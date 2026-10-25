"""Personal MFA Settings visual contract, aligned with Account workspace (#3228)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
MFA = ROOT / 'app/templates/settings/account/partials/_mfa.html'


def source() -> str:
    return MFA.read_text(encoding='utf-8')


def test_mfa_workspace_parses_and_reuses_account_design_language() -> None:
    html = source()
    Environment().parse(html)
    assert '{% import "components/info_tip.html" as info_tip %}' in html
    assert '{% import "components/table_label.html" as table_label %}' in html
    assert "variant='guide'" in html
    assert 'data-account-mfa-workspace="personal-enrollment"' in html
    assert 'rounded-2xl border border-outline-default bg-surface-card' in html
    assert 'bg-kaori-soft text-kaori-primary' in html
    assert 'Account MFA security posture' in html
    assert 'data-account-mfa-posture="cards"' in html
    assert 'md:grid-cols-3' in html


def test_mfa_enrollment_matches_account_natural_action_context_layout() -> None:
    html = source()
    assert 'data-account-mfa-enrollment-layout="action-context"' in html
    assert 'data-account-mfa-recovery-layout="action-context"' in html
    assert 'xl:grid-cols-12 xl:items-start' in html
    assert 'xl:col-span-7' in html
    assert 'xl:col-span-5' in html
    assert 'Enrollment Guide' in html
    assert 'Recovery Security' in html
    assert 'STEP 01' in html
    assert 'STEP 02' in html
    assert 'data-lucide="smartphone"' in html
    assert 'data-lucide="fingerprint"' in html


def test_mfa_fields_are_bounded_and_remain_mobile_responsive() -> None:
    html = source()
    assert html.count('class="max-w-md"') == 2
    assert 'class="max-w-[15rem]"' in html
    assert 'class="max-w-sm"' in html
    assert 'h-11 w-full rounded-lg' in html
    assert 'id="mfa-current-password"' in html
    assert 'id="mfa-confirm-code"' in html
    assert 'id="mfa-regen-password"' in html
    assert 'id="mfa-regen-code"' in html
    assert 'aria-describedby="mfa-confirm-help"' in html
    assert 'inputmode="numeric"' in html
    assert 'pattern="[0-9]{6}"' in html
    assert 'maxlength="6"' in html
    assert 'autocomplete="one-time-code"' in html


def test_mfa_sensitive_mutations_keep_original_server_contracts() -> None:
    html = source()
    assert html.count('name="csrf_token"') == 3
    assert html.count("url_for('settings.account', tab='mfa')") == 3
    for action in ('begin', 'confirm', 'regenerate'):
        assert f'name="mfa_action" value="{action}"' in html
    assert html.count('name="current_password"') == 2
    assert html.count('name="verification_code"') == 2
    assert html.count('autocomplete="current-password"') == 2
    assert '{% if can_change_password %}' in html
    assert '{% if not mfa_state.enrolled %}' in html
    assert '{% if mfa_setup_secret %}' in html
    assert '{% if mfa_recovery_codes %}' in html
    assert '{% for code in mfa_recovery_codes %}' in html
    assert 'name="totp_secret"' not in html
    assert 'name="recovery_hashes"' not in html


def test_mfa_state_is_derived_and_recovery_warnings_remain_visible() -> None:
    html = source()
    assert 'mfa_state.enrolled' in html
    assert 'mfa_state.enrollment_pending' in html
    assert 'mfa_state.policy_mode' in html
    assert 'mfa_state.recovery_count' in html
    assert 'Not Available' in html
    assert 'Not Enrolled' in html
    assert 'status_indicator_label(' in html
    assert 'role="status"' in html
    assert 'One-time recovery codes' in html
    assert 'mfa_recovery_codes' in html
    assert 'mfa_setup_secret' in html
    assert 'will not be shown again' in html
    assert 'data-account-mfa-workspace' in html
    assert 'loading_bar.render(' not in html
    assert 'style=' not in html


def test_mfa_routes_preserve_reauth_and_no_store_secrets() -> None:
    routes = (ROOT / 'app/settings/routes.py').read_text(encoding='utf-8')
    assert "if active_tab == 'mfa' and request.method == 'POST':" in routes
    assert "validate_csrf(request.form.get('csrf_token'))" in routes
    assert 'if not login_fresh():' in routes
    assert "if action in {'begin', 'regenerate'} and user.auth_source == 'database':" in routes
    assert 'mfa_setup_secret = begin_mfa_enrollment(user)' in routes
    assert 'mfa_recovery_codes = confirm_mfa_enrollment(' in routes
    assert 'mfa_recovery_codes = regenerate_mfa_recovery_codes(user)' in routes
    assert "if mfa_setup_secret is not None or mfa_recovery_codes is not None:" in routes
    assert "response.headers['Cache-Control'] = 'no-store'" in routes


def test_mfa_stays_inside_shared_account_tabs_without_new_navigation() -> None:
    page = (ROOT / 'app/templates/settings/account/partials/_page_content.html').read_text(
        encoding='utf-8'
    )
    tabs = (ROOT / 'app/templates/settings/account/partials/_tabs.html').read_text(
        encoding='utf-8'
    )
    assert "active_tab == 'mfa'" in page
    assert '{% include "settings/account/partials/_mfa.html" %}' in page
    assert 'workspace_tabs.render_query_tabs(' in tabs
    assert "'Multi-Factor Authentication', 'shield-check'" in tabs
