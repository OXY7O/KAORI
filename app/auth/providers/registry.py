from __future__ import annotations

from dataclasses import dataclass

from app.auth.providers.base import CredentialAuthProvider
from app.auth.providers.browser import BrowserSsoProvider, SsoProviderError
from app.auth.providers.catalog import AuthProviderType
from app.auth.providers.database import DatabaseAuthProvider
from app.auth.providers.github_oauth import GitHubOAuthProvider
from app.auth.providers.google_oidc import GoogleOidcProvider
from app.auth.providers.ldap import LdapAuthProvider


@dataclass(frozen=True, slots=True)
class CredentialProviderRegistry:
    local: CredentialAuthProvider
    external: tuple[CredentialAuthProvider, ...]


_BROWSER_PROVIDERS: dict[str, BrowserSsoProvider] = {
    AuthProviderType.GOOGLE_OIDC.value: GoogleOidcProvider(),
    AuthProviderType.GITHUB_OAUTH.value: GitHubOAuthProvider(),
}


def build_credential_provider_registry() -> CredentialProviderRegistry:
    return CredentialProviderRegistry(
        local=DatabaseAuthProvider(),
        external=(LdapAuthProvider(),),
    )


def get_browser_sso_provider(provider_type: str) -> BrowserSsoProvider:
    normalized = str(provider_type or '').strip().lower()
    try:
        return _BROWSER_PROVIDERS[normalized]
    except KeyError as exc:
        raise SsoProviderError('The selected provider does not support browser SSO.') from exc


def registered_browser_sso_provider_types() -> tuple[str, ...]:
    return tuple(_BROWSER_PROVIDERS)
