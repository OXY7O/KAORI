"""Bot Protection workspace follows KAORI Access assurance patterns (#3299)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/access/authentication_security/partials/_page_content.html'


def bot_tab() -> str:
    page = TEMPLATE.read_text(encoding='utf-8')
    Environment().parse(page)
    return page.split("{% elif active_tab == 'bot' %}", 1)[1].split(
        '{% else %}\n                {{ assurance.render(',
        1,
    )[0]


def test_bot_tab_has_committed_posture_cards_and_shared_guide() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    tab = bot_tab()
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert "variant='guide'" in tab
    assert "'bot-protection'," in tab
    assert 'bot-protection-guide' in tab
    assert "'Verification Evidence'" in tab
    assert "'Protection Mode'" in tab
    assert "'Verification Adapter'" in tab
    assert "'Provider Configuration'" in tab
    assert "'Enforced' if bot_mode == 'always' else 'Not Enabled'" in tab
    assert "'Configured' if bot_has_secret and bot_site_key and bot_hostname" in tab
    assert 'Saved instance data, not provider health' in tab
    assert 'Cloudflare Siteverify' in tab
    assert 'data-auth-bot-layout="configuration-safety"' in tab
    assert 'grid items-stretch gap-4 xl:grid-cols-5' in tab
    assert 'xl:col-span-3' in tab
    assert 'xl:col-span-2' in tab


def test_bot_controls_have_external_text_heading_and_one_harmonized_hub() -> None:
    tab = bot_tab()
    assert tab.count('data-auth-security-bot-stack="true"') == 1
    assert tab.count('data-auth-security-bot-intro="above-card"') == 1
    assert tab.count('data-auth-security-bot-hub="true"') == 1
    intro = tab.split('data-auth-security-bot-intro="above-card"', 1)[1].split('</header>', 1)[0]
    assert 'Bot Protection Controls' in intro
    assert 'data-lucide=' not in intro
    assert '<span' not in intro
    assert (
        'Configure Cloudflare Turnstile, verify the provider, and review activation safeguards in one workspace.'
        in intro
    )
    assert tab.index('data-auth-security-bot-intro="above-card"') < tab.index(
        'data-auth-security-bot-hub="true"'
    )
    assert tab.index('data-auth-security-bot-hub="true"') < tab.index(
        'data-auth-bot-layout="configuration-safety"'
    )
    assert 'aria-labelledby="auth-security-bot-controls-heading"' in tab
    assert 'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm' in tab
    assert tab.index('data-auth-bot-layout="configuration-safety"') < tab.index('Protection Configuration')
    assert tab.index('Protection Configuration') < tab.index('Activation &amp; Safety')
    assert tab.count('data-auth-bot-layout="configuration-safety"') == 1
    assert 'grid items-stretch gap-4 xl:grid-cols-5' in tab
    assert 'xl:col-span-3' in tab and 'xl:col-span-2' in tab
    assert 'data-auth-bot-activation-layout="balanced"' in tab
    assert 'data-auth-bot-form="configuration"' in tab
    assert 'data-auth-bot-form="verification-test"' in tab
    assert 'class="cf-turnstile"' in tab
    assert 'data-auth-bot-step-context="safety"' in tab


def test_bot_configuration_retains_only_supported_modes_and_safe_mutation() -> None:
    tab = bot_tab()
    assert 'Protection Configuration' in tab
    assert "url_for('access.authentication_security.save_bot_policy')" in tab
    assert 'data-auth-bot-form="configuration"' in tab
    assert 'name="csrf_token"' in tab
    assert 'name="provider_key" value="cloudflare_turnstile"' in tab
    assert 'name="bot_mode"' in tab
    assert 'value="disabled"' in tab
    assert 'value="always"' in tab
    assert 'name="site_key"' in tab
    assert 'name="hostname"' in tab
    assert 'name="secret_key"' in tab
    assert 'autocomplete="new-password"' in tab
    assert 'name="acknowledge_bot_impact"' in tab
    assert 'Change Impact' in tab
    assert 'fails closed and can block sign-in' in tab
    assert 'Save Bot Protection' in tab
    assert 'value="adaptive"' not in tab
    assert 'name="risk_mode"' not in tab
    assert 'type="checkbox"' in tab
    assert 'Protection configuration is read-only for your permission scope.' in tab


def test_bot_activation_uses_existing_live_test_and_does_not_invent_readiness() -> None:
    tab = bot_tab()
    assert 'Activation &amp; Safety' in tab
    assert 'data-auth-bot-activation="ordered"' in tab
    for name in ('Configure Provider', 'Test Verification', 'Enable Protection'):
        assert name in tab
    gate_head = '{% if can_manage_authentication_security and bot_has_secret '
    gate_tail = 'and bot_site_key and bot_hostname %}'
    assert gate_head + gate_tail in tab
    assert "url_for('access.authentication_security.test_bot_provider')" in tab
    assert 'data-auth-bot-form="verification-test"' in tab
    assert 'class="cf-turnstile"' in tab
    assert 'data-sitekey="{{ bot_site_key }}"' in tab
    assert 'data-action="login"' in tab
    assert 'data-size="compact"' in tab
    assert 'https://challenges.cloudflare.com/turnstile/v0/api.js' in tab
    assert 'Test Turnstile' in tab
    assert '{% if bot_tested_at %}' in tab
    assert 'Re-test if older than one hour' in tab
    assert 'Saved configuration is not proof of provider availability' not in tab
    assert 'Stored configuration is not proof of provider availability' in tab
    assert 'whitespace-nowrap' not in tab
    assert 'hx-post=' not in tab
    assert 'data-auth-bot-form="configuration"' in tab
    config_at = tab.index('data-auth-bot-form="configuration"')
    test_at = tab.index('data-auth-bot-form="verification-test"')
    assert config_at < test_at


def test_bot_compact_governance_copy_and_removed_form_help() -> None:
    tab = bot_tab()
    for label, qualifier, detail in (
        ('Challenge Boundary', 'Fail Closed', 'Failed verification blocks sign-in.'),
        ('One-Use Proof', 'Siteverify', 'Cloudflare verifies one-use tokens.'),
        ('Activation Evidence', 'One Hour', 'Always requires fresh proof.'),
        ('Recovery Access', 'Required', 'Confirm recovery before enabling.'),
    ):
        assert f"'{label}', '{qualifier}', '{detail}'" in tab
    assert 'Adaptive mode is deferred until committed risk signals are validated.' not in tab
    assert 'Encrypted at rest; never displayed or recorded in Activity Audit.' not in tab
    assert 'name="secret_key"' in tab
    assert 'type="password"' in tab
    assert 'Change Impact' in tab


def test_bot_activation_stages_fill_panel_with_safe_actionable_guidance() -> None:
    tab = bot_tab()
    assert 'data-auth-bot-activation-layout="balanced"' in tab
    for step in ('configure', 'verify', 'enable'):
        assert f'data-auth-bot-activation-step="{step}"' in tab
    for detail in ('configuration', 'verification', 'safety'):
        assert f'data-auth-bot-step-context="{detail}"' in tab
    for heading in ('Configuration prerequisites', 'One-use verification', 'Activation safeguards'):
        assert heading in tab
    assert 'Stored values do not prove availability.' in tab
    assert 'Proof must be repeated after configuration changes.' in tab
    assert 'Confirm independent recovery access first.' in tab
    assert 'Missing or rejected verification blocks sign-in.' in tab
    assert 'flex-1 flex-col justify-center' in tab
    assert "url_for('access.authentication_security.test_bot_provider')" in tab
    assert 'data-auth-bot-form="verification-test"' in tab
    assert 'class="cf-turnstile"' in tab


def test_bot_server_admission_is_unchanged_and_proof_is_fresh() -> None:
    routes = (ROOT / 'app/access/authentication_security/__init__.py').read_text(encoding='utf-8')
    assert "if request.form.get('acknowledge_bot_impact') != 'yes':" in routes
    assert "if request.form.get('provider_key') != 'cloudflare_turnstile':" in routes
    assert 'mode == BotPolicyMode.ALWAYS' in routes
    assert 'if not ready or config_changed or not recent:' in routes
    assert 'timedelta(hours=1)' in routes
    assert 'policy.bot_tested_at = None' in routes
    assert "request.form.get('cf-turnstile-response')" in routes
    assert 'bot_provider_verified' in routes
    assert "@permission_required('identity_providers.manage')" in routes
