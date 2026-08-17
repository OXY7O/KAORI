from __future__ import annotations

from app.access.authentication.identity_provider.adapters.ldap.client import LdapDirectoryClient
from app.access.authentication.identity_provider.directory import DirectoryProviderAdapter, ExternalIdentity
from app.models import IdentityProvider


class LdapDirectoryAdapter(DirectoryProviderAdapter):
    adapter_key = 'ldap'

    def validate_configuration(self, provider: IdentityProvider) -> str:
        LdapDirectoryClient(provider).validate()
        return f'{provider.display_name} accepted a directory service connection through the LDAP adapter.'

    def search(self, provider: IdentityProvider, query: str) -> list[ExternalIdentity]:
        return LdapDirectoryClient(provider).search(query)
