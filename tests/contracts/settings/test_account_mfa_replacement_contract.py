"""Replacement keeps the existing enrolled MFA workspace and guarded actions (#5357)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_replacement_is_an_enrolled_sibling_with_one_time_provisioning() -> None:
    html = (ROOT / 'app/templates/settings/account/partials/_mfa_replacement.html').read_text(encoding='utf-8')
    Environment().parse(html)
    parent = (ROOT / 'app/templates/settings/account/partials/_mfa.html').read_text(encoding='utf-8')
    assert '{% include "settings/account/partials/_mfa_replacement.html" %}' in parent
    assert '{% if mfa_state.can_replace_authenticator %}' in html
    assert 'mfa_state.replacement_password_label' in html
    assert '{% if mfa_state.replacement_pending %}' in html
    assert '{% if mfa_setup_secret %}' in html
    assert 'name="replacement_totp_secret"' not in html
    assert html.count('name="csrf_token"') == 3
    for action in ('replace_begin', 'replace_confirm', 'replace_cancel'):
        assert f'name="mfa_action" value="{action}"' in html
    assert 'verified provider reauthentication' in html
    routes = (ROOT / 'app/settings/routes.py').read_text(encoding='utf-8')
    assert 'preserve_current_session_after_security_change(' in routes
    assert 'issued_session_version=issued_generation' in routes
    assert "response.headers['Cache-Control'] = 'no-store'" in routes
