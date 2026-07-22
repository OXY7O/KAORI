from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_auth_owns_ldap_protocol_implementation() -> None:
    assert (ROOT / 'app/auth/providers/ldap.py').is_file()
    assert not (ROOT / 'app/users/providers/ldap.py').exists()
    users_sources = '\n'.join(path.read_text() for path in (ROOT / 'app/users').rglob('*.py'))
    assert 'app.users.providers.ldap' not in users_sources


def test_browser_sso_uses_registered_strategy_adapters() -> None:
    routes = (ROOT / 'app/auth/routes.py').read_text()
    registry = (ROOT / 'app/auth/providers/registry.py').read_text()

    assert 'get_browser_sso_provider' in routes
    assert 'GoogleOidcProvider()' in registry
    assert 'GitHubOAuthProvider()' in registry
    assert not (ROOT / 'app/auth/providers/oauth.py').exists()


def test_provider_configuration_branching_is_outside_user_routes() -> None:
    routes = (ROOT / 'app/users/routes.py').read_text()
    configuration = (ROOT / 'app/auth/provider_configuration.py').read_text()

    assert 'apply_identity_provider_configuration(provider, identity_provider_configuration_from_form(form))' in routes
    assert 'validate_identity_provider(provider)' in routes
    assert 'def apply_identity_provider_configuration' in configuration
    assert 'app.users' not in configuration
    assert 'def validate_identity_provider' in configuration
    assert 'def _apply_provider_form' not in routes


def test_retired_auth_provider_feature_flag_is_absent() -> None:
    checked_files = [
        ROOT / 'app/config/default.py',
        ROOT / '.env.example',
        ROOT / '.env.production.example',
    ]
    for path in checked_files:
        assert 'AUTH_ADDITIONAL_PROVIDERS' not in path.read_text()


def test_sso_flow_validation_is_not_reimplemented_in_routes() -> None:
    routes = (ROOT / 'app/auth/routes.py').read_text()
    browser = (ROOT / 'app/auth/providers/browser.py').read_text()

    assert 'sso_flow_is_valid(' in routes
    assert 'def sso_flow_is_valid' in browser
    assert 'compare_digest(' not in routes


def test_identity_model_does_not_duplicate_provider_catalog_predicates() -> None:
    identity_model = (ROOT / 'app/models/identity.py').read_text()

    assert 'def is_ldap' not in identity_model
    assert 'def is_oidc' not in identity_model
    assert 'def is_sso' not in identity_model


def test_required_rate_limiter_fails_fast_instead_of_disabling_security() -> None:
    limiter_source = (ROOT / 'app/extensions/limiter.py').read_text()

    assert 'class _NoopLimiter' not in limiter_source
    assert 'except ImportError' not in limiter_source
    assert 'from flask_limiter import Limiter' in limiter_source
