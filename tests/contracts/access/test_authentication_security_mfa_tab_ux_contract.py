"""MFA administration tab renders committed policy and preserves authorization (#3189)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/access/authentication_security/partials/_page_content.html'


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def _mfa_tab() -> str:
    source = _source()
    return source.split("{% elif active_tab == 'mfa' %}", 1)[1].split("{% elif active_tab == 'bot' %}", 1)[0]


def test_mfa_tab_uses_approved_shared_kaori_visual_components() -> None:
    source = _source()
    Environment().parse(source)
    tab = _mfa_tab()
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert "info_tip.render(" in tab
    assert "variant='guide'" in tab
    assert 'MFA Assurance Policy' in tab
    assert 'Policy Configuration' in tab
    assert 'Enforcement Modes' in tab
    assert 'Account Enrollment &amp; Recovery' in tab
    assert 'sm:grid-cols-3' in tab
    assert 'xl:grid-cols-5' in tab


def test_mfa_tab_displays_effective_committed_policy_without_fake_coverage() -> None:
    tab = _mfa_tab()
    assert "mfa_policy_mode == 'disabled'" in tab
    assert "{{ current_mfa_label }}" in tab
    for mode in ('disabled', 'optional', 'required_privileged', 'required_all'):
        assert f"('{mode}'," in tab
    assert 'Committed KAORI configuration' in tab
    assert 'Every human account must enroll and verify MFA.' in tab
    assert 'No enrollment count' not in tab  # Scope: no invented adoption or coverage statistic.


def test_mfa_policy_form_preserves_server_authority_and_session_impact() -> None:
    tab = _mfa_tab()
    assert "{% if can_manage_authentication_security %}" in tab
    assert "url_for('access.authentication_security.save_mfa_policy')" in tab
    assert 'name="csrf_token"' in tab
    assert 'name="mfa_mode"' in tab
    assert 'name="acknowledge_policy_impact"' in tab
    assert 'required' in tab
    assert 'Save MFA Policy' in tab
    assert 'Changing this policy revokes existing authenticated and Remember Me sessions' in tab
    assert 'Local Database Super Admin' in tab
    assert 'Policy configuration is read-only for your permission scope' in tab


def test_mfa_enrollment_remains_self_service_under_settings() -> None:
    tab = _mfa_tab()
    assert "url_for('settings.account', tab='mfa')" in tab
    assert 'Open My MFA Settings' in tab
    assert 'Administrators cannot retrieve another user' in tab
    assert 'verification_code' not in tab
    assert 'totp_secret' not in tab
    assert 'recovery_hashes' not in tab
    assert 'hx-post=' not in tab


def test_unchanged_router_keeps_viewer_and_manager_permissions() -> None:
    route = (ROOT / 'app/access/authentication_security/__init__.py').read_text(encoding='utf-8')
    assert "@permission_required('identity_providers.view')" in route
    assert "@permission_required('identity_providers.manage')" in route
    assert "requested = MfaPolicyMode(str(request.form.get('mfa_mode') or ''))" in route
    assert "if request.form.get('acknowledge_policy_impact') != 'yes':" in route
    assert "if not any(mfa_enrolled(item.id) for item in recovery_admins):" in route
    assert 'values(auth_session_version=func.coalesce(User.auth_session_version, 1) + 1)' in route
