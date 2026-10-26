"""The four Authentication Security tabs reuse KAORI Role Registry overview grammar (#3305)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
AUTH = ROOT / 'app/templates/access/authentication_security/partials/_page_content.html'
SUMMARY = ROOT / 'app/templates/access/authentication_security/partials/_assurance_summary.html'
ROLES = ROOT / 'app/templates/access/roles/index.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def tabs() -> dict[str, str]:
    source = read(AUTH)
    overview, remaining = source.split("{% if active_tab == 'overview' %}", 1)[1].split(
        "{% elif active_tab == 'mfa' %}", 1
    )
    mfa, remaining = remaining.split("{% elif active_tab == 'bot' %}", 1)
    bot, session = remaining.split(
        "{% else %}\n                {{ assurance.render(",
        1,
    )
    session = 'assurance.render(' + session
    return {'overview': overview, 'mfa': mfa, 'bot': bot, 'sessions': session}


def test_shared_assurance_summary_matches_role_registry_pattern() -> None:
    role = read(ROLES)
    component = read(SUMMARY)
    page = read(AUTH)
    Environment().parse(component)
    Environment().parse(page)
    assert 'Role Registry Overview' in role
    assert 'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4' in role
    assert 'grid gap-3 md:grid-cols-2 xl:grid-cols-4' in role
    assert 'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4' in component
    assert 'grid gap-3 md:grid-cols-2 xl:grid-cols-4' in component
    assert 'rounded-xl border border-outline-subtle bg-surface-card p-3.5' in component
    assert 'table_label.status_indicator_label(status, status_tone)' in component
    assert 'data-auth-assurance-metrics="four"' in component
    assert 'data-auth-assurance-boundaries="four"' in component
    assert 'data-auth-assurance-summary="{{ id }}"' in component
    assert page.count('assurance.render(') == 4


def test_each_tab_starts_with_single_governed_summary() -> None:
    data = tabs()
    expected = {
        'overview': "'authentication-posture',",
        'mfa': "'mfa-policy',",
        'bot': "'bot-protection',",
        'sessions': "'session-security',",
    }
    for name, marker in expected.items():
        tab = data[name]
        assert tab.count('assurance.render(') == 1, name
        assert marker in tab
        assert 'variant=\'guide\'' in tab
        if name == 'bot':
            assert tab.index('assurance.render(') < tab.index('data-auth-bot-layout=')
    assert 'Authentication Assurance Posture' in data['overview']
    assert 'MFA Assurance Policy' in data['mfa']
    assert 'Bot Protection' in data['bot']
    assert 'Session Security' in data['sessions']


def test_mfa_and_bot_policy_forms_remain_server_owned_and_permission_scoped() -> None:
    mfa = tabs()['mfa']
    bot = tabs()['bot']
    assert "url_for('access.authentication_security.save_mfa_policy')" in mfa
    assert 'name="acknowledge_policy_impact"' in mfa
    assert "url_for('settings.account', tab='mfa')" in mfa
    assert "url_for('access.authentication_security.save_bot_policy')" in bot
    assert "url_for('access.authentication_security.test_bot_provider')" in bot
    assert 'name="acknowledge_bot_impact"' in bot
    assert 'name="provider_key" value="cloudflare_turnstile"' in bot
    assert 'data-action="login"' in bot
    assert '{% if can_manage_authentication_security %}' in bot


def test_posture_values_are_factual_without_fake_inventory_or_provider_health() -> None:
    overview = tabs()['overview']
    mfa = tabs()['mfa']
    bot = tabs()['bot']
    session = tabs()['sessions']
    assert 'mfa_policy_mode' in overview
    assert 'bot_mode' in overview
    assert 'bot_has_secret and bot_site_key and bot_hostname' in overview
    assert "'Self-Service'" in mfa
    assert "'TOTP'" in mfa
    assert "'Revocation'" in mfa
    assert "'Recorded' if bot_tested_at else 'Not Recorded'" in bot
    assert "'Configured' if bot_has_secret and bot_site_key and bot_hostname" in bot
    assert "'Disabled'" in bot and "'Always'" in bot
    assert "'Not Qualified'" in session
    assert "'No Inventory'" in session
    assert 'Single active login generation per human account.' in session
    assert 'Provider Setup' in overview
    assert 'Total enrolled users' not in mfa
    assert "'Healthy' if" not in bot
    assert 'Active device count' not in session
