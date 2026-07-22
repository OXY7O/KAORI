from __future__ import annotations

from dataclasses import dataclass

from app.auth.providers.catalog import AuthProviderFamily, provider_family


@dataclass(frozen=True, slots=True)
class IdentitySourceDefinition:
    key: str
    label: str
    credential_owner: str
    provisioning_mode: str
    enabled: bool


UNKNOWN_IDENTITY_SOURCE = IdentitySourceDefinition(
    'unknown',
    'Unknown Identity Source',
    'Unrecognized external source',
    'unsupported',
    False,
)


IDENTITY_SOURCES: tuple[IdentitySourceDefinition, ...] = (
    IdentitySourceDefinition('database', 'Local Database', 'KAORI', 'administrative', True),
    IdentitySourceDefinition('ldap', 'LDAP / Active Directory', 'External directory', 'projection', True),
    IdentitySourceDefinition('sso', 'SSO / Identity Provider', 'External identity provider', 'projection', True),
)


def identity_source_definition(key: str | None) -> IdentitySourceDefinition:
    try:
        family = provider_family(key).value
    except ValueError:
        return UNKNOWN_IDENTITY_SOURCE
    return next((item for item in IDENTITY_SOURCES if item.key == family), UNKNOWN_IDENTITY_SOURCE)


def password_is_managed_by_kaori(identity_source: str | None) -> bool:
    try:
        return provider_family(identity_source) == AuthProviderFamily.DATABASE
    except ValueError:
        return False
