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
    provider_hero = _source('app/templates/integrations/components/_provider_frontpage.html')
    assert 'provider_front.hero(' in landing
    assert 'components/page_hero.html' in provider_hero
    assert 'integrations/components/_provider_frontpage.html' in landing
    assert 'integrations/components/_provider_registration_hero.html' in form
    assert 'integrations/components/_workspace.html' in form
    assert 'integration_ui.section_shell_classes()' in form
    assert "domain.key == 'source_control'" in workspace
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace
    kernel = _source('app/integrations/source_control/source_control/providers/github/kernel_contract.py')
    assert "workspace_endpoint='github_source.index'" in kernel
    assert '<style' not in landing and '<style' not in form
    assert 'integration_tabs.render("github"' in landing
    assert 'integrations/components/_provider_registration_actions.html' in form
    assert 'components/operational_toggle.html' in form
    assert 'integrations/components/_provider_registration_context.html' in form


def test_form_is_csrf_protected_and_admission_gated_in_ui() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    actions = _source('app/templates/integrations/components/_provider_registration_actions.html')
    assert 'form.hidden_tag()' in form
    assert '<fieldset' in form and 'not available' in form
    assert 'type="button"' in form
    assert 'hx-vals=' in form and '"action":"test"' in form
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
    partial = _source('app/templates/integrations/source_control/github/partials/_connection_test_result.html')
    assert 'hx-post=' in form and 'github_source.new_connection' in form
    assert 'hx-include="#github-app-connection-form"' in form
    assert 'hx-target="#github-connection-test-result"' in form
    assert 'hx-disabled-elt="this"' in form
    assert 'form.reportValidity()' in form
    assert 'verify_github_registration_proof(' in routes
    assert routes.index('verify_github_registration_proof(') < routes.index('save_tested_connection(values)')
    assert 'response.status_code = 409' in routes
    assert "response.headers['HX-Trigger']" in routes
    assert "'github-connection-tested'" in routes
    assert 'form.clear_sensitive_fields()' in routes
    assert 'private_key_pem' not in partial
    assert 'webhook_secret' not in partial
    assert 'components/operational_toast.html' in partial
    assert 'toast_oob=true' in partial
    assert 'operational_callout.render(' not in partial


def test_named_register_action_survives_shared_operation_loading_state() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    footer = _source('app/templates/integrations/components/_provider_registration_actions.html')
    shell = _source('app/static/js/application_shell.js')
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')

    assert "submit_name='action'" in form and "submit_value='save'" in form
    assert 'data-operation-submit' in footer
    assert 'name="{{ submit_name }}"' in footer
    assert 'value="{{ submit_value }}"' in footer
    assert 'form.addEventListener(' in shell
    assert "'formdata'" in shell
    assert 'formDataEvent.formData.set(submitName, submitValue)' in shell
    assert shell.index("'formdata'") < shell.index('submitButton.disabled = true')
    assert "if action not in {'test', 'save'}:" in routes
    assert 'verify_github_registration_proof(' in routes


def test_github_registration_persists_then_queues_toast_and_redirects() -> None:
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    layout = _source('app/templates/layouts/app.html')
    notifications = _source('app/platform_operations/notifications/service.py')

    assert routes.index('verify_github_registration_proof(') < routes.index('save_tested_connection(values)')
    assert routes.index('save_tested_connection(values)') < routes.index('record_operational_activity(')
    assert "status='success'" in routes
    assert 'queue_feedback=True' in routes
    assert "return redirect(url_for('github_source.index', tab='registry'))" in routes
    assert 'load_operational_feedback()' in layout
    assert 'components/operational_toast.html' in layout
    assert "return 'toast'" in notifications


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
    assert 'total = ready = grants = None' in routes
    assert 'if available:' in routes
    assert 'Not Observed' in routes
    coverage = _source('app/templates/integrations/source_control/github/partials/_integration_coverage.html')
    assert 'No GitHub Repository Coverage Observed' in coverage
    assert 'integration_tabs.render("github"' in landing
    assert 'provider_front.hero(' in landing


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
    assert "return redirect(url_for('github_source.index', tab='registry'))" in routes  # Post-save.
    assert 'integration_tabs.render("github"' in index
    assert 'integrations/source_control/github/partials/_integration_coverage.html' in index


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


def test_github_connection_registry_reuses_existing_integration_surface() -> None:
    index = _source('app/templates/integrations/source_control/github/index.html')
    registry = _source('app/templates/integrations/source_control/github/partials/_connection_registry.html')
    shared_hero = _source('app/templates/integrations/components/_provider_frontpage.html')
    tabs = _source('app/templates/components/integration_workspace_tabs.html')
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')

    assert 'provider_front.hero(' in index
    assert 'provider_front.overview(' in index
    assert 'integration_tabs.render("github", active_tab, stats.grants, stats.total)' in index
    assert 'components/framed_workspace_tabs.html' in tabs
    assert "association_label='Consumer Bindings'" in shared_hero
    assert 'association_label="Repository Grants"' in index
    assert 'provider_registry.registry_header(' in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'provider_registry.pagination_footer(' in registry
    assert 'components/states/_empty_state.html' in registry
    assert 'integration_status(' in registry
    assert 'github_source_uat.detail' in registry
    assert 'if uat_workspace_enabled and installation' in registry
    assert 'data-kaori-github-connection-registry' in registry
    assert "if target == 'github-connection-registry':" in routes
    assert "'integrations/source_control/github/partials/_connection_registry.html'" in routes
    assert 'paginate_query(' in routes
    assert "requested_per_page = request.args.get('per_page', 5, type=int) or 5" in routes
    assert "integration_type='source_control'," in routes
    assert "provider_key='github'," in routes
    assert 'SourceRepositoryGrant.valid_until.is_(None)' in routes
    assert 'if available:' in routes
    assert 'require_uat_access()' in routes
    assert "return redirect(url_for('github_source.index', tab='registry'))" in routes
    assert 'queue_feedback=True' in routes
    assert '<style' not in registry and '<script' not in registry


def test_github_coverage_reuses_kubernetes_table_contract_and_committed_state() -> None:
    github = _source('app/templates/integrations/source_control/github/partials/_integration_coverage.html')
    kubernetes = _source(
        'app/templates/integrations/orchestration/container_orchestrator/providers/'
        'kubernetes/partials/_integration_coverage.html'
    )
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')

    for shared_pattern in (
        'provider_registry.registry_header(',
        'integration_ui.filter_region_classes()',
        'provider_registry.search_field(',
        'provider_registry.select_field(',
        'provider_registry.asset_coverage_table_classes()',
        'provider_registry.asset_coverage_colgroup()',
        'integration_status(',
        'provider_registry.pagination_footer(',
        'components/states/_empty_state.html',
    ):
        assert shared_pattern in github and shared_pattern in kubernetes

    for column in ('Repository', 'Installation', 'Environment', 'Access', 'Evidence Coverage', 'Actions'):
        assert f'>{column}</th>' in github
    assert 'hx-target="#github-integration-coverage"' in github
    assert 'hx-swap="outerHTML"' in github
    assert 'name="coverage_page"' in github
    assert 'name="coverage_per_page"' in github
    assert '"coverage_page"' in github and '"coverage_per_page"' in github
    assert 'No GitHub Repository Coverage Observed' in github
    assert 'Register Connection' in github
    assert 'if uat_workspace_enabled' in github
    assert '<style' not in github and '<script' not in github

    assert "requested_coverage_page = request.args.get('coverage_page', 1, type=int) or 1" in routes
    assert "requested_coverage_per_page = request.args.get('coverage_per_page', 5, type=int) or 5" in routes
    assert 'SourceRepositoryCollectionState.committed_generation > 0' in routes
    assert "'coverage_observed': committed_collections > 0" in routes
    assert 'No Repositories in Committed Coverage' in github
    assert 'Review committed GitHub repository access and coverage.' in github
    assert 'Register and validate a GitHub App, then collect repository evidence.' in github
    assert 'SourceRepositoryGrant.valid_until.is_(None)' in routes
    assert "SourceInstallation.provider_key == 'github'" in routes
    assert "SourceRepository.host_key == 'github.com'" in routes
    assert 'coverage_rows, coverage_pagination = paginate_query(' in routes
    assert "if target == 'github-integration-coverage':" in routes
    assert 'selected_coverage_query or selected_coverage_environment or selected_coverage_status' in routes
    assert 'selected_coverage_environment' in routes
    assert 'selected_coverage_status' in routes
    assert 'integrations/source_control/github/partials/_integration_coverage.html' in routes
    assert "return redirect(url_for('github_source.index', tab='registry'))" in routes


def test_github_identity_fields_share_one_responsive_desktop_row() -> None:
    form = _source('app/templates/integrations/source_control/github/form.html')
    installation = form.split('data-kaori-github-app-access', 1)[1].split('App Credentials', 1)[0]

    assert 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3' in installation
    assert '[form.app_id, form.installation_id, form.account_id]' in installation
    assert 'min-w-0' in installation
    assert 'form.hidden_tag()' in form
    assert 'connection_test_proof' in form


def test_github_coverage_empty_state_guides_registered_installations_to_validation_and_sync() -> None:
    coverage = _source('app/templates/integrations/source_control/github/partials/_integration_coverage.html')
    routes = _source('app/integrations/source_control/source_control/providers/github/application/routes.py')
    uat = _source('app/integrations/source_control/source_control/providers/github/application/uat_routes.py')

    assert '{% elif registered %}' in coverage
    assert 'Complete Full Validation, then Sync Repositories to commit repository access evidence.' in coverage
    assert "url_for('github_source.index', tab='registry')" in coverage
    assert 'View Connections' in coverage
    assert 'No GitHub Repository Coverage Observed' in coverage
    assert 'No Repositories in Committed Coverage' in coverage
    assert 'Register and validate a GitHub App, then collect repository evidence.' in coverage
    assert "url_for('github_source.new_connection')" in coverage
    assert '{% if coverage_has_active_filters %}' in coverage

    # Registration persists identity, not repository inventory. Coverage
    # requires a separately committed grant generation.
    assert 'SourceRepositoryCollectionState.committed_generation > 0' in routes
    assert 'SourceRepositoryGrant.valid_until.is_(None)' in routes
    assert "'registered': total" in routes
    assert "operation='full_validation'" in uat
    assert 'enqueue_source_repository_sync(' in uat
