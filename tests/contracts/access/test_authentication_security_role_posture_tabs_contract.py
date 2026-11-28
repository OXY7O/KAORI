"""The five Authentication Security tabs reuse KAORI Role Registry overview grammar (#3305)."""

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
    bot, remaining = remaining.split("{% elif active_tab == 'login-protection' %}", 1)
    login, session = remaining.split(
        '{% else %}\n                {{ assurance.render(',
        1,
    )
    session = 'assurance.render(' + session
    login += read(AUTH.parent / '_login_protection_controls.html')
    return {'overview': overview, 'mfa': mfa, 'bot': bot, 'login-protection': login, 'sessions': session}


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
    assert page.count('assurance.render(') == 5


def test_each_tab_starts_with_single_governed_summary() -> None:
    data = tabs()
    expected = {
        'overview': "'authentication-posture',",
        'mfa': "'mfa-policy',",
        'bot': "'bot-protection',",
        'login-protection': "'login-protection-posture',",
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
    assert 'macro control_header(id, title, description, status, status_tone, icon, guide=none)' in shared
    assert 'data-auth-security-card-header="{{ id }}"' in shared
    assert 'table_label.status_indicator_label(status, status_tone)' in shared
    for name, tab in data.items():
        key = 'session' if name == 'sessions' else name
        intro = 'control' if name == 'overview' else key
        hub_marker = f'data-auth-security-{key}-hub="true"'
        intro_marker = f'data-auth-security-{intro}-intro="above-card"'
        assert tab.count('assurance.control_header(') == 1, name
        assert tab.count(hub_marker) == 1
        assert intro_marker in tab
        assert tab.index(intro_marker) < tab.index(hub_marker) < tab.index('assurance.control_header(')
        posture, controls = tab.split('assurance.control_header(', 1)
        assert 'metadata=table_label.metadata_label(' in posture
        assert 'guide=info_tip.render(' not in posture
        assert controls.count('guide=info_tip.render(') == 1
        assert 'overflow-visible rounded-2xl' in posture
    assert '{% if metadata %}{{ metadata }}{% endif %}' in shared
    assert '{% if guide %}{{ guide }}{% endif %}' in shared
    assert source.count('assurance.render(') == 5
    assert source.count('assurance.control_header(') == 4  # Login Protection header lives in its existing partial.


def test_control_header_statuses_come_from_committed_security_state() -> None:
    data = tabs()
    overview = data['overview']
    mfa = data['mfa']
    bot = data['bot']
    session = data['sessions']
    assert "'Controls Enabled' if mfa_active or bot_active or lockout_mode == 'enforced'" in overview
    assert "'Policy Active' if mfa_policy_mode != 'disabled' else 'Disabled'" in mfa
    assert "'Enforced' if bot_mode == 'always' else 'Disabled'" in bot
    assert "'Policy Configured'" in session
    assert "'info'" in session
    assert "'monitor-check'" in session


def test_session_detail_hub_uses_committed_policy_and_preserves_inventory_boundary() -> None:
    session = tabs()['sessions']
    partial = read(AUTH.parent / '_session_policy_controls.html')
    Environment().parse(partial)
    assert 'Session Security Controls' in session
    assert 'Session Policy & Enforcement' in session
    assert 'data-auth-security-session-stack="true"' in session
    assert 'session_policy.privileged_idle_minutes' in session
    assert 'session_policy.regular_absolute_hours' in session
    assert 'session_policy.regular_remember' in session
    assert 'data-auth-session-layout="policy-enforcement"' in partial
    assert 'grid items-stretch gap-4 p-4 lg:p-5 xl:grid-cols-5' in partial
    assert 'xl:col-span-3' in partial and 'xl:col-span-2' in partial
    assert 'Outside Current Scope' in partial
    assert "table_label.status_indicator_label('Not Qualified', 'unknown')" in partial
    assert 'No active-device inventory or remote session registry is claimed.' in partial
    assert 'Active device count' not in session + partial
    assert 'Idle and absolute session timeouts are not qualified' not in session + partial


def test_session_configuration_is_server_owned_and_permission_scoped() -> None:
    partial = read(AUTH.parent / '_session_policy_controls.html')
    assert '{% if can_manage_authentication_security %}' in partial
    manager, viewer = partial.split('{% if can_manage_authentication_security %}', 1)[1].split('{% else %}', 1)
    assert "url_for('access.authentication_security.save_session_policy')" in manager
    assert 'name="csrf_token"' in manager
    assert 'name="acknowledge_session_policy_impact"' in manager
    for field in (
        'session_privileged_idle_minutes',
        'session_privileged_absolute_hours',
        'session_regular_idle_minutes',
        'session_regular_absolute_hours',
        'session_regular_remember',
        'session_warning_minutes',
    ):
        assert field in manager
    assert 'Policy configuration is read-only for your permission scope.' in viewer
    assert '<form' not in viewer
    assert 'hx-post=' not in partial
    assert 'whitespace-nowrap' not in partial


def test_session_assurance_descriptions_fit_desktop_without_forced_truncation() -> None:
    session = tabs()['sessions']
    for detail in (
        'Provider disablement revokes sessions.',
        'Requests check committed deadlines.',
        'Never bypasses server deadlines.',
    ):
        assert detail in session
        assert len(detail) <= 40
    summary = read(SUMMARY)
    assert '{{ detail }}' in summary
    assert 'whitespace-nowrap' not in summary
    assert 'text-ellipsis' not in summary


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
    assert "'Policy Configured'" in session
    assert "'No Inventory'" in session
    assert 'Single active login generation per human account.' in session
    assert 'Provider Setup' in overview
    assert 'Total enrolled users' not in mfa
    assert "'Healthy' if" not in bot
    assert 'Active device count' not in session
