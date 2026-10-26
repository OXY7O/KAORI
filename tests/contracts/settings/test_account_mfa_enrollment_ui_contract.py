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


def test_mfa_guide_precedes_two_responsive_enrollment_cards() -> None:
    html = source()
    assert 'data-account-mfa-enrollment-layout="guide-over-steps"' in html
    assert 'data-account-mfa-steps="paired"' in html
    assert 'xl:grid-cols-2 xl:items-stretch' in html
    assert 'sm:grid-cols-2 xl:grid-cols-4' in html
    assert 'Confirm your password or sign in again.' in html
    assert 'Scan QR or enter the setup key.' in html
    assert 'Confirm your local password or use a fresh external sign-in.' not in html
    assert 'Scan the QR code or enter the setup key into a compatible TOTP application.' not in html
    assert 'whitespace-nowrap' not in html
    assert 'data-account-mfa-recovery-layout="action-context"' in html
    assert 'xl:grid-cols-12 xl:items-start' in html
    assert 'xl:col-span-7' in html  # Enrolled recovery only.
    assert 'xl:col-span-5' in html  # Enrolled recovery only.
    assert 'How to Activate MFA' in html
    assert 'Recovery Security' in html
    assert 'STEP 01' in html
    assert 'STEP 02' in html
    assert 'data-lucide="smartphone"' in html
    assert 'data-lucide="fingerprint"' in html
    assert html.index('data-account-mfa-guide="single-panel"') < html.index('data-account-mfa-steps="paired"')
    assert html.index('data-account-mfa-steps="paired"') < html.index('id="account-mfa-step-one"')
    assert html.index('id="account-mfa-step-one"') < html.index('id="account-mfa-step-two"')


def test_mfa_fields_are_bounded_and_remain_mobile_responsive() -> None:
    html = source()
    assert html.count('class="max-w-md"') == 1  # Enrolled recovery password only.
    assert 'class="max-w-[21rem]"' not in html
    assert 'class="max-w-sm"' in html  # Enrolled recovery verification remains bounded.
    enrollment = html.split('data-account-mfa-steps="paired"', 1)[1].split('{% else %}', 1)[0]
    assert enrollment.count('<div class="w-full">') == 2
    assert 'id="mfa-current-password"' in enrollment
    assert 'id="mfa-confirm-code"' in enrollment
    assert 'placeholder="Confirm your current password"\n                                           class="h-12 w-full' in enrollment
    assert 'h-11 w-full rounded-lg' in html
    assert 'id="mfa-current-password"' in html
    assert 'id="mfa-confirm-code"' in html
    assert 'id="mfa-regen-password"' in html
    assert 'id="mfa-regen-code"' in html
    assert 'mfa-confirm-help' not in html
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
    assert 'mfa_feedback' not in html
    assert 'data-mfa-one-time-provisioning="true"' in html
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
    assert 'if mfa_setup_secret is not None or mfa_recovery_codes is not None:' in routes
    assert "response.headers['Cache-Control'] = 'no-store'" in routes


def test_mfa_stays_inside_shared_account_tabs_without_new_navigation() -> None:
    page = (ROOT / 'app/templates/settings/account/partials/_page_content.html').read_text(encoding='utf-8')
    tabs = (ROOT / 'app/templates/settings/account/partials/_tabs.html').read_text(encoding='utf-8')
    assert "active_tab == 'mfa'" in page
    assert '{% include "settings/account/partials/_mfa.html" %}' in page
    assert 'workspace_tabs.render_query_tabs(' in tabs
    assert "'Multi-Factor Authentication', 'shield-check'" in tabs


def test_approved_mockup_has_illustrative_hero_and_posture_cards() -> None:
    html = source()
    assert 'Add an authenticator application to protect your KAORI account' in html
    assert 'border-b border-outline-default bg-surface-card px-5 py-4' in html
    assert 'border-b border-outline-default bg-surface-card px-5 py-4' in html
    assert 'data-lucide="smartphone"' in html
    assert 'data-lucide="shield-check"' in html
    assert 'data-lucide="settings"' in html
    assert 'bg-status-warning-soft text-status-warning-text' in html
    assert 'Account MFA security posture' in html
    assert 'table_label.status_indicator_label(' in html


def test_approved_mockup_uses_single_guide_above_balanced_step_cards() -> None:
    html = source()
    for n in ('1', '2', '3', '4'):
        assert f'aria-hidden="true">{n}</span>' in html
    assert 'Generate Setup Key</h3>' in html
    assert 'Verify Your Authenticator</h3>' in html
    assert 'data-account-mfa-enrollment-layout="guide-over-steps"' in html
    assert 'grid gap-4 xl:grid-cols-2 xl:items-stretch' in html
    assert 'flex min-w-0 flex-col rounded-xl border border-outline-default' in html
    assert html.count('data-account-mfa-guide="single-panel"') == 1
    assert 'mt-auto border-t border-outline-subtle' in html
    assert 'sm:grid-cols-2 xl:grid-cols-4' in html
    assert 'xl:grid-cols-12 xl:items-stretch' not in html


def test_otp_remains_one_native_accessible_field_with_visual_digit_spacing() -> None:
    html = source()
    assert html.count('id="mfa-confirm-code"') == 1
    assert html.count('name="verification_code"') == 2  # Confirm and regeneration only.
    assert 'maxlength="6"' in html
    assert 'pattern="[0-9]{6}"' in html
    assert 'tracking-widest' in html
    assert 'tracking-[' not in html
    assert 'text-center font-mono text-lg' in html
    assert 'mfa-confirm-help' not in html
    assert 'role="note"' in html
    assert 'Security Information' in html
    assert 'otpauth://' not in html  # No fabricated QR provisioning or inline URI.


def test_mfa_feedback_review_has_one_clear_guide_with_four_steps() -> None:
    html = source()
    assert html.count('data-account-mfa-guide="single-panel"') == 1
    assert 'How to Activate MFA' in html
    for title in (
        'Generate a setup key',
        'Add an authenticator app',
        'Verify the six-digit code',
        'Save recovery codes',
    ):
        assert title in html
    assert 'Need help?' in html
    assert 'If setup fails, sign in again and confirm your current password.' in html
    assert 'border border-kaori-primary/20 bg-kaori-soft/60' not in html
    assert 'Six digits from your authenticator application.' not in html


def test_one_time_authenticator_provisioning_exposes_local_qr_and_manual_fallback() -> None:
    html = source()
    assert '{% if mfa_setup_secret %}' in html
    assert '{% if mfa_setup_qr_src %}' in html
    assert 'Scan QR Code' in html
    assert 'Manual Setup Key' in html
    assert 'src="{{ mfa_setup_qr_src }}"' in html
    assert 'alt="Scan this one-time QR code with an authenticator app"' in html
    assert '{{ mfa_setup_secret }}' in html
    assert 'data-mfa-one-time-provisioning="true"' in html
    assert 'mfa_feedback' not in html
    assert 'qrserver.com' not in html
    assert 'chart.googleapis.com' not in html


def test_account_partial_uses_existing_operational_toast_oob() -> None:
    page = (ROOT / 'app/templates/settings/account/partials/_page_content.html').read_text(encoding='utf-8')
    assert '{% if mfa_toast %}' in page
    assert 'status=mfa_toast.status' in page
    assert 'activity_audit_saved=mfa_toast.activity_audit_saved' in page
    assert 'toast_oob=true' in page
    assert '{% include "components/operational_toast.html" %}' in page


def test_mfa_backend_queues_full_page_feedback_and_protects_one_time_response() -> None:
    routes = (ROOT / 'app/settings/routes.py').read_text(encoding='utf-8')
    assert 'mfa_toast: dict[str, Any] | None = None' in routes
    assert 'build_totp_qr_data_uri(mfa_setup_secret, account_label=user.username)' in routes
    assert 'if not is_htmx:\n            queue_operational_feedback(mfa_toast)' in routes
    assert "'mfa_toast': mfa_toast if is_htmx else None" in routes
    assert "response.headers['Cache-Control'] = 'no-store'" in routes
    assert "response.headers['Pragma'] = 'no-cache'" in routes
    assert "response.headers['Referrer-Policy'] = 'no-referrer'" in routes
    assert 'activity_audit_saved=True' in routes
    assert 'notification_deck_visible=False' in routes
    assert 'mfa_feedback' not in routes
