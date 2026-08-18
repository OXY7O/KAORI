#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOCS = (
    'docs/design/KAORI_AUTHENTICATION_SURFACE_LOCK_V1.md',
    'docs/design/audits/KAORI_AUTHENTICATION_SURFACE_FINAL_LOCK_AUDIT_2026_08_11.md',
)

ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
ARBITRARY_TRACKING = re.compile(r'\btracking-\[[^\]]+\]')
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)
SCRIPT_TAG = re.compile(r'<script\b(?P<attrs>[^>]*)>', re.I | re.S)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _inline_script_count(source: str) -> int:
    return sum(1 for match in SCRIPT_TAG.finditer(source) if not re.search(r'\bsrc\s*=', match.group('attrs'), re.I))


def main() -> int:
    errors: list[str] = []

    templates = sorted((ROOT / 'app/templates/access/authentication').rglob('*.html'))
    require(bool(templates), 'Authentication templates are missing', errors)

    for path in templates:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not ARBITRARY_TEXT.search(source), f'{relative}: arbitrary text size is forbidden', errors)
        require(not ARBITRARY_TRACKING.search(source), f'{relative}: arbitrary tracking is forbidden', errors)
        require('font-extrabold' not in source, f'{relative}: font-extrabold is forbidden', errors)
        require(' uppercase ' not in f' {source} ', f'{relative}: visible uppercase utility is forbidden', errors)
        require(not INLINE_HANDLER.search(source), f'{relative}: inline DOM handler is forbidden', errors)

    routes = read('app/access/authentication/routes.py')
    session_source = read('app/access/authentication/session.py')
    forms = read('app/access/authentication/forms.py')
    services = read('app/access/authentication/services.py')
    audit = read('app/access/authentication/audit.py')
    production = read('app/config/production.py')
    default_config = read('app/config/default.py')
    login = read('app/templates/access/authentication/partials/_login_form.html')
    alerts = read('app/templates/access/authentication/partials/_login_alerts.html')
    index = read('app/templates/access/authentication/index.html')
    setup = read('app/templates/access/authentication/setup_required.html')
    layout = read('app/templates/layouts/auth.html')
    login_css = read('app/static/css/auth-login.css')
    login_js = read('app/static/js/auth_login.js')
    readme = read('app/access/authentication/README.md')
    quality_gate = read('scripts/quality_gate.sh')
    feature_gate = read('scripts/verify_feature_test_coverage.py')

    for required in (
        "@auth_bp.route('/login', methods=['GET', 'POST'])",
        'AUTH_LOGIN_RATE_LIMIT',
        "form.next.data = safe_next_url(request.args.get('next')) or ''",
        'message = credential_failure_message(result)',
        "@auth_bp.route('/logout', methods=['POST'])",
        '@login_required',
        'logout_user()',
        'clear_authenticated_session()',
        "'state_hash': state_fingerprint(state)",
        'generate_nonce() if adapter.requires_nonce else None',
        'AUTH_SSO_FLOW_TTL_SECONDS',
    ):
        require(required in routes, f'Authentication route contract missing: {required}', errors)

    for required in (
        'def safe_next_url(',
        "not candidate.startswith('/')",
        "candidate.startswith('//')",
        "if '\\\\' in candidate",
        'parsed.scheme or parsed.netloc',
        'session.clear()',
        "current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)",
        "session['_remember'] = 'clear'",
    ):
        require(required in session_source, f'Authentication session contract missing: {required}', errors)

    require('form.hidden_tag()' in login, 'Login form must keep Flask-WTF CSRF ownership', errors)
    require('autocomplete="username"' in login, 'Username autocomplete contract missing', errors)
    require('autocomplete="current-password"' in login, 'Password autocomplete contract missing', errors)
    require('data-password-toggle' in login, 'Password visibility control missing', errors)
    require('aria-label="Show password"' in login, 'Password visibility control must be accessible', errors)
    require('id="auth-theme-toggle"' in login, 'Authentication theme control missing', errors)
    require('aria-label="Switch to Dark Mode"' in login, 'Authentication theme action label missing', errors)
    require('Remember Me' in login, 'Remember Me control missing', errors)
    require(
        'provider_login_url' in login and 'next=form.next.data' in login,
        'SSO safe-next propagation missing',
        errors,
    )
    require('aria-live="polite"' in alerts, 'Login feedback must expose an aria-live region', errors)
    require('role="alert"' in alerts and 'role="status"' in alerts, 'Login feedback semantics drifted', errors)
    require('aria-label="KAORI sign in"' in index, 'Login shell accessibility label missing', errors)
    require(
        '{% block title %}Sign In · KAORI{% endblock title %}' in index,
        'Login document title must use KAORI Title Case',
        errors,
    )
    require('aria-labelledby="setup-required-title"' in setup, 'Setup-required accessibility contract missing', errors)
    for required in (
        'Run the Initial KAORI Database Bootstrap',
        'Manual Initialization Commands',
        'Encryption Key Requirement',
        'Missing Schema Objects',
        'PostgreSQL Is Unavailable',
    ):
        require(required in setup, f'Setup Required Title Case contract missing: {required}', errors)

    require('username = StringField' in forms and 'Length(max=100)' in forms, 'Username input bound missing', errors)
    require('password = PasswordField' in forms and 'Length(max=1024)' in forms, 'Password input bound missing', errors)
    require('return INVALID_LOGIN_MESSAGE' in services, 'Credential failure normalization missing', errors)
    require(
        'authenticated_actor = user if user is not None and (success or is_logout) else None' in audit,
        'Authentication actor/target audit boundary missing',
        errors,
    )

    for required in (
        'SESSION_COOKIE_SECURE = True',
        'SESSION_COOKIE_HTTPONLY = True',
        "SESSION_COOKIE_SAMESITE = 'Lax'",
        'REMEMBER_COOKIE_SECURE = True',
        'REMEMBER_COOKIE_HTTPONLY = True',
        "REMEMBER_COOKIE_SAMESITE = 'Lax'",
    ):
        require(required in production, f'Production cookie contract missing: {required}', errors)
    for required in (
        'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(',
        "'AUTH_REMEMBER_ME_DAYS',",
        'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)',
        'AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME = _env_bool(',
    ):
        require(required in default_config, f'Remember-me configuration contract missing: {required}', errors)

    require('width: min(1060px, 100%);' in login_css, 'Compact login width contract drifted', errors)
    require('height: 44px;' in login_css, 'Compact control height contract drifted', errors)
    require(
        '@media (max-height: 760px) and (min-width: 1024px)' in login_css,
        '14-inch compact-height contract missing',
        errors,
    )
    require('#7C3AED' in login_css and '#A78BFA' in login_css, 'KAORI Violet login palette contract drifted', errors)

    require("filename='js/auth_login.js'" in layout, 'Authentication runtime must use first-party JS', errors)
    require(_inline_script_count(layout) == 1, 'Only the pre-paint theme bootstrap may remain inline', errors)
    require("localStorage.getItem('theme')" in layout, 'Pre-paint theme bootstrap missing', errors)
    require("querySelector('[data-password-input]')" in login_js, 'External password-toggle runtime missing', errors)
    require("getElementById('auth-theme-toggle')" in login_js, 'External theme-toggle runtime missing', errors)
    require(
        'const actionLabel = `Switch to ${nextTheme} Mode`' in login_js,
        'Theme-toggle accessible state label missing',
        errors,
    )
    require(
        "themeToggle.setAttribute('aria-label', actionLabel)" in login_js,
        'Theme-toggle aria-label update missing',
        errors,
    )
    require("localStorage.setItem('theme'" in login_js, 'Theme preference persistence missing', errors)

    for relative in LOCK_DOCS:
        require((ROOT / relative).exists(), f'missing Authentication lock artifact: {relative}', errors)
    for required in (
        'Authentication Surface v1 is final-locked',
        'compact 14-inch presentation contract',
        'safe redirect',
        'super-admin remember-me',
        'Integration: N/A',
    ):
        require(required in readme, f'Authentication README final-lock contract missing: {required}', errors)
    require(
        'verify_authentication_surface_final_lock.py' in quality_gate,
        'Authentication Surface Final Lock verifier is not release-gated',
        errors,
    )

    for relative in (
        'tests/unit/access/authentication/test_auth_session_policy.py',
        'tests/access/authentication/test_login_characterization.py',
        'tests/security/access/authentication/test_authentication_security.py',
        'tests/rendering/access/authentication/test_authentication_rendering.py',
        'tests/e2e/access/authentication/test_authentication_smoke.py',
    ):
        require(relative in feature_gate, f'Authentication release evidence is not registered: {relative}', errors)

    if errors:
        print('FAIL — KAORI Authentication Surface Final Lock v1')
        for error in errors:
            print(f'- {error}')
        return 1

    print(f'PASS — KAORI Authentication Surface Final Lock v1 · {len(templates)} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
