from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.definitions.loader import load_definition_document
from app.definitions.validation import require_bool, require_list, require_mapping, require_str, unique_by


class AuthProviderFamily(StrEnum):
    DATABASE = 'database'
    LDAP = 'ldap'
    SSO = 'sso'


class AuthProviderType(StrEnum):
    DATABASE = 'database'
    LDAP = 'ldap'
    GOOGLE_OIDC = 'google_oidc'
    GITHUB_OAUTH = 'github_oauth'


class AuthFlow(StrEnum):
    CREDENTIALS = 'credentials'
    BROWSER = 'browser'


@dataclass(frozen=True, slots=True)
class AuthProviderDefinition:
    provider_type: AuthProviderType
    family: AuthProviderFamily
    label: str
    flow: AuthFlow
    configurable: bool
    supports_jit: bool = False


def _load_provider_definitions() -> tuple[AuthProviderDefinition, ...]:
    document = load_definition_document('auth/providers.yaml', expected_kind='auth_providers')
    raw_items = [
        require_mapping(item, f'providers[{index}]')
        for index, item in enumerate(require_list(document.get('providers'), 'providers'))
    ]
    unique_by(raw_items, 'provider_type', 'providers')
    output: list[AuthProviderDefinition] = []
    for index, raw in enumerate(raw_items):
        path = f'providers[{index}]'
        output.append(
            AuthProviderDefinition(
                provider_type=AuthProviderType(require_str(raw, 'provider_type', path)),
                family=AuthProviderFamily(require_str(raw, 'family', path)),
                label=require_str(raw, 'label', path),
                flow=AuthFlow(require_str(raw, 'flow', path)),
                configurable=require_bool(raw, 'configurable', path),
                supports_jit=require_bool(raw, 'supports_jit', path, default=False),
            )
        )
    return tuple(output)


_PROVIDER_DEFINITIONS = _load_provider_definitions()
_PROVIDER_BY_TYPE = {definition.provider_type.value: definition for definition in _PROVIDER_DEFINITIONS}


def provider_definition(provider_type: str | AuthProviderType) -> AuthProviderDefinition:
    normalized = str(provider_type or '').strip().lower()
    try:
        return _PROVIDER_BY_TYPE[normalized]
    except KeyError as exc:
        raise ValueError(f'Unsupported authentication provider type: {provider_type!r}.') from exc


def provider_family(provider_type: str | AuthProviderType | None) -> AuthProviderFamily:
    normalized = str(provider_type or '').strip().lower()
    if not normalized:
        return AuthProviderFamily.DATABASE
    definition = _PROVIDER_BY_TYPE.get(normalized)
    if definition is None:
        raise ValueError(f'Unsupported authentication provider type: {provider_type!r}.')
    return definition.family


def provider_label(provider_type: str | AuthProviderType | None) -> str:
    normalized = str(provider_type or '').strip().lower()
    if not normalized or normalized == 'local':
        normalized = AuthProviderType.DATABASE.value
    if normalized == 'credentials':
        return 'Credential Sign-In'
    if normalized == AuthProviderFamily.SSO.value:
        return 'Browser SSO'
    definition = _PROVIDER_BY_TYPE.get(normalized)
    if definition is not None:
        return definition.label
    return normalized.replace('_', ' ').title() or 'Unknown Provider'


def provider_types_for_family(family: str | AuthProviderFamily) -> tuple[str, ...]:
    normalized = AuthProviderFamily(str(family).strip().lower())
    return tuple(
        definition.provider_type.value for definition in _PROVIDER_DEFINITIONS if definition.family == normalized
    )


def configurable_provider_choices() -> list[tuple[str, str]]:
    return [
        (definition.provider_type.value, definition.label)
        for definition in _PROVIDER_DEFINITIONS
        if definition.configurable
    ]


def browser_sso_provider_types() -> tuple[str, ...]:
    return tuple(
        definition.provider_type.value for definition in _PROVIDER_DEFINITIONS if definition.flow == AuthFlow.BROWSER
    )


def is_browser_sso_provider_type(provider_type: str | None) -> bool:
    return str(provider_type or '').strip().lower() in browser_sso_provider_types()
