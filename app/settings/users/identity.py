from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentitySourceDefinition:
    key: str
    label: str
    credential_owner: str
    provisioning_mode: str
    enabled: bool


IDENTITY_SOURCES: tuple[IdentitySourceDefinition, ...] = (
    IdentitySourceDefinition('database', 'Local Database', 'KAORI', 'administrative', True),
    IdentitySourceDefinition('ldap', 'LDAP / Active Directory', 'External directory', 'projection', False),
    IdentitySourceDefinition('sso', 'SSO / Identity Provider', 'External identity provider', 'projection', False),
)


def identity_source_definition(key: str | None) -> IdentitySourceDefinition:
    normalized = (key or 'database').strip().lower()
    return next((item for item in IDENTITY_SOURCES if item.key == normalized), IDENTITY_SOURCES[0])


def password_is_managed_by_kaori(identity_source: str | None) -> bool:
    return identity_source_definition(identity_source).key == 'database'
