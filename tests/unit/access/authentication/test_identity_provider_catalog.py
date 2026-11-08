from app.access.authentication.identity_provider.catalog import (
    BrowserPkcePolicy,
    BrowserProtocol,
    browser_provider_profile,
    provider_definition,
)


def test_browser_provider_profiles_separate_protocol_from_provider_identity() -> None:
    google = browser_provider_profile('google')
    github = browser_provider_profile('github')

    assert google.protocol == BrowserProtocol.OIDC
    assert google.scopes == ('openid', 'email', 'profile')
    assert google.discovery_url == 'https://accounts.google.com/.well-known/openid-configuration'
    assert google.identity_resolver_key == 'oidc_claims'
    assert google.pkce_policy == BrowserPkcePolicy.PREFERRED
    assert dict(google.authorization_parameters) == {'prompt': 'select_account'}

    assert github.protocol == BrowserProtocol.OAUTH2
    assert github.scopes == ('read:user', 'user:email')
    assert github.authorization_url == 'https://github.com/login/oauth/authorize'
    assert github.token_url == 'https://github.com/login/oauth/access_token'
    assert github.userinfo_url == 'https://api.github.com/user'
    assert github.identity_resolver_key == 'github'
    assert github.pkce_policy == BrowserPkcePolicy.PREFERRED
    assert dict(github.authorization_parameters) == {'allow_signup': 'false'}


def test_non_browser_providers_do_not_expose_browser_profiles() -> None:
    assert provider_definition('database').browser_profile is None
    assert provider_definition('ldap_directory').browser_profile is None
