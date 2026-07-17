from __future__ import annotations

from dataclasses import dataclass

from app.auth.providers.base import AuthProvider
from app.auth.providers.database import DatabaseAuthProvider
from app.auth.providers.ldap import LdapAuthProvider


@dataclass(frozen=True)
class ProviderRegistry:
    local: AuthProvider
    external: tuple[AuthProvider, ...]


def build_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        local=DatabaseAuthProvider(),
        external=(LdapAuthProvider(),),
    )
