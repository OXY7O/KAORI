from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


_PROVIDER_DEFINITIONS: tuple[AuthProviderDefinition, ...] = (
    AuthProviderDefinition(
        provider_type=AuthProviderType.DATABASE,
        family=AuthProviderFamily.DATABASE,
        label='Local Database',
        flow=AuthFlow.CREDENTIALS,
        configurable=False,
    ),
    AuthProviderDefinition(
        provider_type=AuthProviderType.LDAP,
        family=AuthProviderFamily.LDAP,
        label='LDAP / Active Directory',
        flow=AuthFlow.CREDENTIALS,
        configurable=True,
    ),
    AuthProviderDefinition(
        provider_type=AuthProviderType.GOOGLE_OIDC,
        family=AuthProviderFamily.SSO,
        label='Google OpenID Connect',
        flow=AuthFlow.BROWSER,
        configurable=True,
        supports_jit=True,
    ),
    AuthProviderDefinition(
        provider_type=AuthProviderType.GITHUB_OAUTH,
        family=AuthProviderFamily.SSO,
        label='GitHub OAuth',
        flow=AuthFlow.BROWSER,
        configurable=True,
        supports_jit=True,
    ),
)

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


def provider_types_for_family(family: str | AuthProviderFamily) -> tuple[str, ...]:
    normalized = AuthProviderFamily(str(family).strip().lower())
    return tuple(
        definition.provider_type.value
        for definition in _PROVIDER_DEFINITIONS
        if definition.family == normalized
    )


def configurable_provider_choices() -> list[tuple[str, str]]:
    return [
        (definition.provider_type.value, definition.label)
        for definition in _PROVIDER_DEFINITIONS
        if definition.configurable
    ]


def browser_sso_provider_types() -> tuple[str, ...]:
    return tuple(
        definition.provider_type.value
        for definition in _PROVIDER_DEFINITIONS
        if definition.flow == AuthFlow.BROWSER
    )


def is_browser_sso_provider_type(provider_type: str | None) -> bool:
    return str(provider_type or '').strip().lower() in browser_sso_provider_types()
