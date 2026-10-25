"""GitHub App setup inherits KAORI integration UX and security boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_onboarding_reuses_shared_kaori_components_not_new_css() -> None:
    landing = _source('app/templates/integrations/source_control/github/index.html')
    form = _source('app/templates/integrations/source_control/github/form.html')
    workspace = _source('app/templates/integrations/partials/_domain_workspace.html')
    assert 'components/page_hero.html' in landing
    assert 'integrations/components/_provider_frontpage.html' in landing
    assert 'integrations/components/_provider_registration_hero.html' in form
    assert 'integrations/components/_workspace.html' in form
    assert 'integration_ui.section_shell_classes()' in form
    assert "domain.key == 'source_control'" in workspace
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    kernel = _source('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    assert "workspace_endpoint='github_source.index'" in kernel
    assert '<style' not in landing and '<style' not in form
    assert 'text-kaori-primary' in landing
    assert 'integrations/components/_provider_registration_actions.html' in form
    assert 'components/operational_toggle.html' in form
    assert 'integrations/components/_provider_registration_context.html' in form


def test_form_is_csrf_protected_and_admission_gated_in_ui() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    actions = _source('app/templates/integrations/components/_provider_registration_actions.html')
    assert 'form.hidden_tag()' in form
    assert '<fieldset' in form and 'not available' in form
    assert 'type="button"' in form
    assert 'hx-vals=\'{"action":"test"}\'' in form
    assert "submit_name='action'" in form
    assert "submit_value='save'" in form
    assert 'disabled' in actions
    assert 'x-bind:disabled="!connectionVerified"' in actions
    assert 'autocomplete="off"' in form
    assert 'form.webhook_secret' in form and 'form.private_key_pem' in form
    assert 'x-on:input.capture="invalidateConnectionTest($event)"' in form
    assert 'x-on:change.capture="invalidateConnectionTest($event)"' in form
    assert 'x-on:github-connection-tested.window="applyConnectionTest($event)"' in form
    assert 'name="connection_test_proof"' in form


def test_connection_test_stays_inline_and_registration_is_proof_gated() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    partial = _source(
        'app/templates/integrations/source_control/github/partials/_connection_test_result.html'
    )
    assert "hx-post=" in form and "github_source.new_connection" in form
    assert 'hx-include="#github-app-connection-form"' in form
    assert 'hx-target="#github-connection-test-result"' in form
    assert 'hx-disabled-elt="this"' in form
    assert 'form.reportValidity()' in form
    assert 'verify_github_registration_proof(' in routes
    assert routes.index('verify_github_registration_proof(') < routes.index('save_tested_connection(values)')
    assert 'response.status_code = 409' in routes
    assert "response.headers['HX-Trigger']" in routes
    assert "'github-connection-tested'" in routes
    assert "form.clear_sensitive_fields()" in routes
    assert 'private_key_pem' not in partial
    assert 'webhook_secret' not in partial


def test_github_registration_uses_canonical_kaori_form_sections_and_footer() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    identity = form.index('Connection Identity')
    installation = form.index('GitHub App Installation')
    credentials = form.index('App Credentials')
    controls = form.index('Operational Controls')
    actions = form.index('registration_actions.render(')
    context = form.index('registration_context.render(')

    assert identity < installation < credentials < controls < actions < context
    assert 'integration_ui.palette_icon("settings-2", "brand", size="lg")' in form
    assert 'operational_toggle.render("Allow KAORI to Use This Connection"' in form
    assert 'form.enabled' in form
    assert 'form.private_key_pem' in form
    assert 'form.webhook_secret' in form
    assert 'GitHub App Registration Flow' in form
    assert 'data-kaori-provider-registration-context' not in form  # Macro owns markup.
    assert 'xl:col-span-8' in form and 'xl:col-span-4' in form
    assert 'xl:sticky xl:top-5' in form
    assert 'registration_actions.render(' in form
    assert 'components/connection_validation_header.html' in form
    assert 'connection_validation_header.render(' in form
    assert 'data-kaori-github-app-access' in form
    assert form.index('connection_validation_header.render(') < form.index('hx-vals=')
    assert form.index('hx-vals=') < form.index('registration_actions.render(')
    assert "submit_value='save'" in form
    assert 'connection_test_proof' in form
    assert 'data-operation-submit' not in form  # Shared registration macro owns loading state.
    assert "loading_label='Registering Connection...'" in form
    assert "url_for('github_source.index')" in form
    assert 'url_for("integrations.source_control")' in form
    assert 'bg-kaori-primary px-4' not in form
    assert 'rounded-lg border border-outline-default bg-surface-card px-4 py-2' not in form


def test_server_checks_rbac_and_blocks_post_before_reading_secrets() -> None:
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    assert "@permission_required('integrations.manage')" in routes
    assert "if request.method == 'POST' and not available:" in routes
    assert 'abort(409)' in routes
    assert 'form.validate_on_submit()' in routes
    assert 'form.clear_sensitive_fields()' in routes
    assert "'Cache-Control'] = 'no-store, max-age=0'" in routes
    assert 'record_operational_activity(' in routes
    assert 'save_tested_connection(values)' in routes


def test_planned_provider_does_not_fake_inventory_zero_or_ready() -> None:
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    landing = _source('app/templates/integrations/source_control/github/index.html')
    assert 'registered: int | None = None' in routes
    assert 'ready: int | None = None' in routes
    assert 'if available:' in routes
    assert 'Not Observed' in landing
    assert 'Repository Evidence' in landing
    assert 'Connection Registry' in landing
    assert 'Choose Provider' in landing


def test_blueprint_is_registered_using_existing_bootstrap() -> None:
    bootstrap = _source('app/bootstrap/blueprints.py')
    assert (
        'from app.integrations.source_control.source_control.providers.github.application.routes '
        'import github_source_bp'
    ) in bootstrap
    assert 'github_source_bp,' in bootstrap
    assert "url_prefix='/integrations/source-control/github'" in _source(
        'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )


def test_source_control_selects_provider_then_opens_existing_registration() -> None:
    kernel = _source('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    form = _source('app/templates/integrations/source_control/github/form.html')
    index = _source('app/templates/integrations/source_control/github/index.html')

    assert "workspace_endpoint='github_source.index'" in kernel
    assert "@github_source_bp.route('/connections/new', methods=['GET', 'POST'])" in routes
    assert 'integrations/components/_provider_registration_hero.html' in form
    assert 'registration_hero.render(' in form
    assert 'Register GitHub App Connection' in form
    assert "url_for('github_source.index')" in form  # Shared Back to Registry.
    assert "return redirect(url_for('github_source.index'))" in routes  # Post-save.
    assert (
        '"Choose Provider", url_for("integrations.choose_integration_provider", integration_type="source_control")'
    ) in index
    assert 'Manage Installations' in index


def test_source_control_operational_templates_have_no_temporary_uat_copy() -> None:
    for name in ('index.html', 'form.html', 'uat_index.html', 'uat_detail.html'):
        template = _source(f'app/templates/integrations/source_control/github/{name}')
        assert 'UAT' not in template, name
        assert 'planned' not in template.lower(), name
        assert 'design review' not in template.lower(), name

    domain = _source('app/templates/integrations/partials/_domain_workspace.html')
    assert 'Source Control Connections' in domain
    assert 'GitHub App onboarding remains planned' not in domain
    # Endpoint names remain internal; permission and admission gates stay intact.
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    assert 'require_uat_access()' in routes
    assert "@permission_required('integrations.manage')" in routes
    assert "if request.method == 'POST' and not available:" in routes
