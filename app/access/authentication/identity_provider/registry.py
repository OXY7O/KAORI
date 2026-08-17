from __future__ import annotations

from dataclasses import dataclass

from app.access.authentication.identity_provider.adapters.ldap.credential import LdapCredentialAdapter
from app.access.authentication.identity_provider.adapters.ldap.directory import LdapDirectoryAdapter
from app.access.authentication.identity_provider.browser import BrowserSsoAdapter, SsoProviderError
from app.access.authentication.identity_provider.credential import CredentialAuthAdapter
from app.access.authentication.identity_provider.directory import DirectoryProviderAdapter, DirectoryProviderError
from app.access.authentication.identity_provider.providers.github.browser import GitHubOAuthAdapter
from app.access.authentication.identity_provider.providers.google.browser import GoogleOidcAdapter
from app.access.authentication.local_database import DatabaseAuthProvider


@dataclass(frozen=True, slots=True)
class CredentialProviderRegistry:
    local: DatabaseAuthProvider
    external: tuple[CredentialAuthAdapter, ...]


_CREDENTIAL_ADAPTERS: dict[str, CredentialAuthAdapter] = {
    LdapCredentialAdapter.adapter_key: LdapCredentialAdapter(),
}


_DIRECTORY_ADAPTERS: dict[str, DirectoryProviderAdapter] = {
    LdapDirectoryAdapter.adapter_key: LdapDirectoryAdapter(),
}


_BROWSER_ADAPTERS: dict[str, BrowserSsoAdapter] = {
    GoogleOidcAdapter.adapter_key: GoogleOidcAdapter(),
    GitHubOAuthAdapter.adapter_key: GitHubOAuthAdapter(),
}


def build_credential_provider_registry() -> CredentialProviderRegistry:
    return CredentialProviderRegistry(local=DatabaseAuthProvider(), external=tuple(_CREDENTIAL_ADAPTERS.values()))


def get_directory_provider_adapter(adapter_key: str) -> DirectoryProviderAdapter:
    normalized = str(adapter_key or '').strip().lower()
    try:
        return _DIRECTORY_ADAPTERS[normalized]
    except KeyError as exc:
        raise DirectoryProviderError(
            'The selected identity provider adapter does not support directory provisioning.'
        ) from exc


def registered_directory_adapter_keys() -> tuple[str, ...]:
    return tuple(_DIRECTORY_ADAPTERS)


def get_browser_sso_adapter(adapter_key: str) -> BrowserSsoAdapter:
    normalized = str(adapter_key or '').strip().lower()
    try:
        return _BROWSER_ADAPTERS[normalized]
    except KeyError as exc:
        raise SsoProviderError('The selected identity provider adapter does not support browser SSO.') from exc


def registered_browser_sso_adapter_keys() -> tuple[str, ...]:
    return tuple(_BROWSER_ADAPTERS)
