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
        '{% else %}\n                {{ assurance.render(',
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
        assert "variant='guide'" in tab
        if name == 'bot':
            assert tab.index('assurance.render(') < tab.index('data-auth-bot-layout=')
    assert 'Authentication Assurance Posture' in data['overview']
    assert 'MFA Assurance Policy' in data['mfa']
    assert 'Bot Protection' in data['bot']
    assert 'Session Security' in data['sessions']


def test_every_tab_has_shared_header_inside_single_accessible_control_hub() -> None:
    data = tabs()
    source = read(AUTH)
    shared = read(SUMMARY)
    Environment().parse(source)
    Environment().parse(shared)
    assert '{% macro control_header(id, title, description, status, status_tone, icon) -%}' in shared
    assert 'data-auth-security-card-header="{{ id }}"' in shared
    assert 'table_label.status_indicator_label(status, status_tone)' in shared
    for name, tab in data.items():
        assert tab.count('assurance.control_header(') == 1, name
        assert tab.count(f'data-auth-security-{name if name != "sessions" else "session"}-hub="true"') == 1
        intro = 'control' if name == 'overview' else name if name != 'sessions' else 'session'
        assert f'data-auth-security-{intro}-intro="above-card"' in tab
        header_index = tab.index('assurance.control_header(')
        hub_index = tab.index(f'data-auth-security-{name if name != "sessions" else "session"}-hub="true"')
        intro_index = tab.index(f'data-auth-security-{intro}-intro="above-card"')
        assert intro_index < hub_index < header_index
    assert source.count('assurance.render(') == 4
    assert source.count('assurance.control_header(') == 4


def test_control_header_statuses_come_from_committed_security_state() -> None:
    data = tabs()
    overview = data['overview']
    mfa = data['mfa']
    bot = data['bot']
    session = data['sessions']
    assert "'Controls Enabled' if mfa_active or bot_active else 'Optional Controls Disabled'" in overview
    assert "'Policy Active' if mfa_policy_mode != 'disabled' else 'Disabled'" in mfa
    assert "'Enforced' if bot_mode == 'always' else 'Disabled'" in bot
    assert "'Generation Active'" in session
    assert "'info'" in session
    assert "'monitor-check'" in session


def test_session_detail_hub_describes_only_confirmed_read_only_boundaries() -> None:
    session = tabs()['sessions']
    assert 'Session Security Controls' in session
    assert 'data-auth-security-session-stack="true"' in session
    assert 'data-auth-session-boundaries="read-only"' in session
    assert 'Governed in Access' in session
    assert 'Outside Current Scope' in session
    assert 'Protected requests validate the committed login generation.' in session
    assert 'New logins and provider disablement revoke affected prior sessions.' in session
    assert 'Idle and absolute session timeouts are not qualified as enforced controls.' in session
    assert 'No active-device inventory or remote session registry is claimed.' in session
    assert '<form' not in session
    assert 'hx-post=' not in session
    assert 'Active device count' not in session


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
