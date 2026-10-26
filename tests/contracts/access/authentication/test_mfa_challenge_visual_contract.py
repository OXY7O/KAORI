"""The pending MFA sign-in challenge reuses KAORI auth surfaces (#3290)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / 'app/templates/access/authentication/mfa_challenge.html'


def source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_mfa_challenge_keeps_a_single_pending_authentication_form() -> None:
    html = source()
    Environment().parse(html)
    assert '{% extends "layouts/auth.html" %}' in html
    assert html.count('<form method="post"') == 1
    assert '{{ form.hidden_tag() }}' in html
    assert html.count('form.verification_code(') == 1
    assert html.count('form.submit(') == 1
    assert 'autocomplete="one-time-code"' in html
    assert 'maxlength="64"' in html
    assert 'inputmode="text"' in html
    assert 'form.verification_code.errors' in html
    assert 'role="alert"' in html
    assert "url_for('auth.login')" in html
    assert 'Start a New Sign In' in html
    assert 'data-kaori-mfa-challenge="centered-header"' in html


def test_mfa_challenge_centered_header_has_concise_accurate_copy() -> None:
    html = source()
    assert 'data-kaori-mfa-challenge-header="centered"' in html
    assert 'class="text-center"' in html
    assert 'mx-auto flex h-14 w-14' in html
    assert 'Multi-Factor Authentication' in html
    assert 'Verify Your Sign In' in html
    assert 'Use your authenticator app or a recovery code.' in html
    assert 'Access continues after successful verification.' in html
    assert 'This page does not grant application access' not in html
    assert 'w-full max-w-lg' in html
    assert 'mx-auto mt-3 max-w-sm' in html
    assert 'whitespace-nowrap' not in html
    assert 'tracking-[' not in html
    assert 'text-[' not in html
    assert 'qr-code' not in html
    assert 'qr-scanner' not in html


def test_mfa_challenge_template_keeps_existing_server_authentication_boundary() -> None:
    routes = (ROOT / 'app/access/authentication/routes.py').read_text(encoding='utf-8')
    assert "@auth_bp.route('/mfa', methods=['GET', 'POST'])" in routes
    assert 'MFA_PENDING_SESSION_KEY' in routes
    assert 'form.validate_on_submit()' in routes
    assert "kind = verify_mfa_challenge(user, str(form.verification_code.data or ''))" in routes
    assert 'mfa_verified=True' in routes
    assert "render_template('access/authentication/mfa_challenge.html', form=form, error=error)" in routes
