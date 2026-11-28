"""Replacement keeps the existing enrolled MFA workspace and guarded actions (#5357)."""

from pathlib import Path

from jinja2 import DictLoader, Environment

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


def test_sso_replacement_renders_guidance_without_any_mutation_form() -> None:
    html = (ROOT / 'app/templates/settings/account/partials/_mfa_replacement.html').read_text(encoding='utf-8')
    # Use the real workspace markup with lightweight component macro stubs.
    env = Environment(
        loader=DictLoader({
            'replacement.html': html,
            'components/info_tip.html': '{% macro render(id, title, text, items, placement, variant) %}{% endmacro %}',
            'components/table_label.html': '{% macro status_indicator_label(text, tone) %}{{ text }}{% endmacro %}',
        })
    )
    rendered = env.get_template('replacement.html').render(
        mfa_state={
            'can_replace_authenticator': False,
            'replacement_browser_sso': True,
            'replacement_pending': False,
            'replacement_expired': False,
        }
    )
    assert 'Unavailable' in rendered
    assert 'does not have a qualified strict reauthentication flow' in rendered
    assert 'governed MFA recovery' in rendered
    assert '<form' not in rendered
    assert 'replacement_password' not in rendered
    assert 'replace_confirm' not in rendered
