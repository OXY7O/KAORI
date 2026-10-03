#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []

    required_paths = (
        'app/access/authentication/identity_provider/catalog.py',
        'app/access/authentication/identity_provider/configuration.py',
        'app/access/authentication/identity_provider/registry.py',
        'app/access/authentication/identity_provider/credential.py',
        'app/access/authentication/identity_provider/directory.py',
        'app/access/authentication/identity_provider/adapters/ldap/client.py',
        'app/access/authentication/identity_provider/adapters/ldap/credential.py',
        'app/access/authentication/identity_provider/adapters/ldap/directory.py',
        'app/access/authentication/identity_provider/providers/google/browser.py',
        'app/access/authentication/identity_provider/providers/github/browser.py',
        'app/access/identity_providers/routes.py',
        'app/access/identity_providers/forms.py',
        'app/access/identity_providers/service.py',
        'app/definitions/catalogs/access/authentication/identity_provider/providers.yaml',
        'app/templates/access/identity_providers/index.html',
    )
    for path in required_paths:
        if not (ROOT / path).exists():
            errors.append(f'missing canonical Identity Provider path: {path}')

    forbidden_paths = (
        'app/access/authentication/providers',
        'app/access/authentication/provider_configuration.py',
        'app/access/users/provider_forms.py',
        'app/access/users/external.py',
        'app/access/users/provisioning_proof.py',
        'app/templates/access/users/providers',
        'app/templates/access/users/external_identities.html',
        'app/definitions/catalogs/access/authentication/providers.yaml',
    )
    for path in forbidden_paths:
        if (ROOT / path).exists():
            errors.append(f'legacy product-first Identity Provider path remains: {path}')

    model = read('app/models/identity.py')
    for required in ('provider_key:', 'adapter_key:', 'configuration_json:', 'admission_policy_json:'):
        if required not in model:
            errors.append(f'IdentityProvider model missing canonical field: {required}')
    for forbidden in ('provider_type:', 'server_uri:', 'oidc_client_id:', 'allowed_domains:', 'allowed_subjects:'):
        if forbidden in model:
            errors.append(f'IdentityProvider model retains adapter/product-specific field: {forbidden}')

    catalog = read('app/access/authentication/identity_provider/catalog.py')
    if 'load_definition_document(' not in catalog:
        errors.append('Identity Provider provider definitions must be loaded from the source-controlled catalog')
    if 'AuthProviderType' in catalog:
        errors.append('Identity Provider core must not restore a product enum')
    for required in ('BrowserProtocol', 'BrowserPkcePolicy', 'BrowserProviderProfile', 'browser_profile'):
        if required not in catalog:
            errors.append(f'Identity Provider catalog missing reusable browser profile contract: {required}')

    provider_catalog = read('app/definitions/catalogs/access/authentication/identity_provider/providers.yaml')
    for required in (
        'browser_profile:',
        'protocol: oidc',
        'protocol: oauth2',
        'identity_resolver_key: oidc_claims',
        'identity_resolver_key: github',
        'pkce_policy: preferred',
    ):
        if required not in provider_catalog:
            errors.append(f'Identity Provider provider catalog missing browser profile authority: {required}')

    routes = read('app/access/identity_providers/routes.py')
    if "url_prefix='/access/identity-providers'" not in routes:
        errors.append('Identity Provider administrative workspace must own /access/identity-providers')
    if 'get_directory_provider_adapter(selected_provider.adapter_key)' not in routes:
        errors.append('Directory provisioning must dispatch by adapter_key')
    for forbidden in ('LdapDirectoryClient(selected_provider)', 'provider.provider_type'):
        if forbidden in routes:
            errors.append(f'Identity Provider application route contains provider-specific dispatch: {forbidden}')

    registry = read('app/access/authentication/identity_provider/registry.py')
    for required in ('_CREDENTIAL_ADAPTERS', '_DIRECTORY_ADAPTERS', '_BROWSER_ADAPTERS'):
        if required not in registry:
            errors.append(f'Identity Provider adapter registry missing: {required}')

    form_js = read('app/static/js/identity_provider_form.js')
    for forbidden in ('google_oidc', 'github_oauth', "=== 'google'", "=== 'github'", "=== 'ldap'"):
        if forbidden in form_js:
            errors.append(f'Identity Provider core form JS contains product/adapter-specific branch: {forbidden}')

    integration_contract = read('docs/authentication/PROVIDER_INTEGRATION_CONTRACT.md')
    architecture = read('docs/authentication/AUTHENTICATION_ARCHITECTURE.md')
    for required in (
        'Browser Protocol and Provider Profile Contract',
        'OAuth 2.0 alone is not a universal identity protocol',
        'Provider-specific identity resolvers',
    ):
        if required not in integration_contract:
            errors.append(f'Identity Provider integration contract missing reusable browser authority: {required}')
    for required in ('Browser Protocol / Provider Separation', 'reusable oidc adapter', 'reusable oauth2 transport'):
        if required not in architecture:
            errors.append(f'Authentication architecture missing reusable browser extension authority: {required}')

    login = read('app/templates/access/authentication/partials/_login_form.html')
    if 'provider.provider_type' in login:
        errors.append('Login surface must render provider identity from catalog, not provider_type branches')
    if 'row.definition.icon' not in login:
        errors.append('Login surface must render provider presentation from catalog definition')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print('PASS — KAORI Identity Provider Architecture')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
