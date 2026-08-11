from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_login_and_logout_keep_csrf_and_post_only_boundaries() -> None:
    routes = read('app/auth/routes.py')
    login = read('app/templates/auth/partials/_login_form.html')

    assert "@auth_bp.route('/login', methods=['GET', 'POST'])" in routes
    assert "@auth_bp.route('/logout', methods=['POST'])" in routes
    assert '@login_required' in routes.split("@auth_bp.route('/logout'", 1)[1]
    assert '<form class="mt-6 space-y-4" method="POST">' in login
    assert 'form.hidden_tag()' in login


def test_production_authentication_cookies_are_secure_http_only_and_same_site() -> None:
    production = read('app/config/production.py')

    for required in (
        'SESSION_COOKIE_SECURE = True',
        'SESSION_COOKIE_HTTPONLY = True',
        "SESSION_COOKIE_SAMESITE = 'Lax'",
        'REMEMBER_COOKIE_SECURE = True',
        'REMEMBER_COOKIE_HTTPONLY = True',
        "REMEMBER_COOKIE_SAMESITE = 'Lax'",
    ):
        assert required in production


def test_authentication_failures_do_not_claim_target_as_actor_or_expose_provider_state() -> None:
    audit = read('app/auth/audit.py')
    services = read('app/auth/services.py')

    assert 'authenticated_actor = user if user is not None and (success or is_logout) else None' in audit
    assert 'return INVALID_LOGIN_MESSAGE' in services
    credential_failure = services.split('def credential_failure_message(', 1)[1].split('\n\n__all__', 1)[0]
    assert 'PROVIDER_UNAVAILABLE_MESSAGE' not in credential_failure
