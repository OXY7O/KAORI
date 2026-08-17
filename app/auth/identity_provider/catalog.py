from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.definitions.loader import load_definition_document
from app.definitions.validation import require_bool, require_list, require_mapping, require_str, unique_by


class AuthProviderFamily(StrEnum):
    DATABASE = 'database'
    DIRECTORY = 'directory'
    SSO = 'sso'


class AuthFlow(StrEnum):
    CREDENTIALS = 'credentials'
    BROWSER = 'browser'


@dataclass(frozen=True, slots=True)
class IdentityProviderDefinition:
    provider_key: str
    adapter_key: str
    family: AuthProviderFamily
    label: str
    short_label: str
    icon: str
    flow: AuthFlow
    configurable: bool
    supports_jit: bool
    configuration_profile: str
    admission_policy: str
    description: str
    enabled_copy: str
    admission_label: str
    admission_help: str
    client_secret_placeholder: str
    guidance_partial: str


def _load_provider_definitions() -> tuple[IdentityProviderDefinition, ...]:
    document = load_definition_document(
        'auth/identity_provider/providers.yaml',
        expected_kind='identity_providers',
    )
    raw_items = [
        require_mapping(item, f'providers[{index}]')
        for index, item in enumerate(require_list(document.get('providers'), 'providers'))
    ]
    unique_by(raw_items, 'provider_key', 'providers')
    output: list[IdentityProviderDefinition] = []
    for index, raw in enumerate(raw_items):
        path = f'providers[{index}]'
        output.append(
            IdentityProviderDefinition(
                provider_key=require_str(raw, 'provider_key', path),
                adapter_key=require_str(raw, 'adapter_key', path),
                family=AuthProviderFamily(require_str(raw, 'family', path)),
                label=require_str(raw, 'label', path),
                short_label=require_str(raw, 'short_label', path),
                icon=require_str(raw, 'icon', path),
                flow=AuthFlow(require_str(raw, 'flow', path)),
                configurable=require_bool(raw, 'configurable', path),
                supports_jit=require_bool(raw, 'supports_jit', path, default=False),
                configuration_profile=require_str(raw, 'configuration_profile', path),
                admission_policy=require_str(raw, 'admission_policy', path),
                description=require_str(raw, 'description', path),
                enabled_copy=require_str(raw, 'enabled_copy', path),
                admission_label=require_str(raw, 'admission_label', path),
                admission_help=require_str(raw, 'admission_help', path),
                client_secret_placeholder=require_str(raw, 'client_secret_placeholder', path, allow_empty=True),
                guidance_partial=require_str(raw, 'guidance_partial', path, allow_empty=True),
            )
        )
    return tuple(output)


_PROVIDER_DEFINITIONS = _load_provider_definitions()
_PROVIDER_BY_KEY = {definition.provider_key: definition for definition in _PROVIDER_DEFINITIONS}


def provider_definitions() -> tuple[IdentityProviderDefinition, ...]:
    return _PROVIDER_DEFINITIONS


def configurable_provider_definitions() -> tuple[IdentityProviderDefinition, ...]:
    return tuple(definition for definition in _PROVIDER_DEFINITIONS if definition.configurable)


def provider_definition(provider_key: str | None) -> IdentityProviderDefinition:
    normalized = str(provider_key or '').strip().lower()
    try:
        return _PROVIDER_BY_KEY[normalized]
    except KeyError as exc:
        raise ValueError(f'Unsupported identity provider key: {provider_key!r}.') from exc


def provider_label(provider_key: str | None) -> str:
    normalized = str(provider_key or '').strip().lower()
    if not normalized or normalized == 'local':
        normalized = 'database'
    if normalized == 'credentials':
        return 'Credential Sign-In'
    if normalized == 'identity_provider':
        return 'External Identity Provider'
    definition = _PROVIDER_BY_KEY.get(normalized)
    if definition is not None:
        return definition.label
    return normalized.replace('_', ' ').title() or 'Unknown Provider'


def provider_keys_for_family(family: str | AuthProviderFamily) -> tuple[str, ...]:
    normalized = AuthProviderFamily(str(family).strip().lower())
    return tuple(definition.provider_key for definition in _PROVIDER_DEFINITIONS if definition.family == normalized)


def configurable_provider_choices() -> list[tuple[str, str]]:
    return [(definition.provider_key, definition.label) for definition in configurable_provider_definitions()]


def browser_provider_keys() -> tuple[str, ...]:
    return tuple(definition.provider_key for definition in _PROVIDER_DEFINITIONS if definition.flow == AuthFlow.BROWSER)


def browser_adapter_keys() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            definition.adapter_key for definition in _PROVIDER_DEFINITIONS if definition.flow == AuthFlow.BROWSER
        )
    )


def is_browser_provider_key(provider_key: str | None) -> bool:
    return str(provider_key or '').strip().lower() in browser_provider_keys()
