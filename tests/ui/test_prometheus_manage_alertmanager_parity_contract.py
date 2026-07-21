from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / 'app/prometheus/routes.py'
SERVICE = ROOT / 'app/prometheus/service.py'
FORMS = ROOT / 'app/prometheus/forms.py'
PRESENTATION = ROOT / 'app/prometheus/presentation.py'
DETAIL = ROOT / 'app/templates/prometheus/instance_detail.html'
CONFIGURATION = ROOT / 'app/templates/prometheus/partials/_detail_configuration.html'
VALIDATION = ROOT / 'app/templates/prometheus/partials/_detail_validation.html'
VALIDATION_CONTENT = ROOT / 'app/templates/prometheus/partials/_detail_validation_content.html'
RUNTIME = ROOT / 'app/templates/prometheus/partials/_detail_runtime.html'
RUNTIME_PANEL = ROOT / 'app/templates/prometheus/partials/_runtime_panel.html'
RUNTIME_HISTORY = ROOT / 'app/templates/prometheus/partials/_runtime_history.html'
SCOPE = ROOT / 'app/templates/prometheus/partials/_detail_scope.html'
STANDARD = ROOT / 'docs/design/components/INTEGRATION_MANAGE_WORKSPACE.md'
AUDIT = ROOT / 'docs/design/audits/PROMETHEUS_MANAGE_ALERTMANAGER_PARITY_AUDIT_2026_07.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_configuration_is_inline_and_legacy_edit_redirects() -> None:
    routes = read(ROUTES)
    detail = read(DETAIL)
    configuration = read(CONFIGURATION)

    assert "@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])" in routes
    assert "@prometheus_bp.get('/instances/<int:instance_id>/edit')" in routes
    assert "return redirect(url_for('prometheus.instance_detail'" in routes
    assert "render_template(\n        'prometheus/instance_form.html'" not in routes[routes.index('def edit_instance'):routes.index("@prometheus_bp.get('/instances')")]
    assert "action=\"{{ url_for('prometheus.instance_detail', instance_id=instance.id) }}#configuration\"" in configuration
    assert 'Save Changes' in configuration
    assert 'Edit Configuration' not in detail + configuration
    assert "url_for('prometheus.edit_instance'" not in detail + configuration


def test_configuration_uses_alertmanager_workspace_components() -> None:
    configuration = read(CONFIGURATION)

    assert configuration.count('workspace_summary_card.render') == 3
    assert "'Connection Contract'" in configuration
    assert "'Change Impact'" in configuration
    assert "'Integration Flow'" in configuration
    assert "info_flow.render(\n                'Configuration Flow'" in configuration
    assert 'Instance Configuration' in configuration
    assert 'Endpoint &amp; Access' in configuration
    assert 'Compatibility Detection' in configuration
    assert 'Security &amp; Operational Controls' in configuration
    assert 'related_page_card.render' in configuration


def test_validation_exposes_full_technical_capability_contract() -> None:
    validation = read(VALIDATION)
    content = read(VALIDATION_CONTENT)
    presentation = read(PRESENTATION)

    assert validation.count('workspace_summary_card.render') == 3
    required = (
        'Capability Technical Detail',
        'Latest Evidence',
        'Why KAORI Checks This',
        'Technical Checks',
        'Full PromQL Query',
        'Success Criteria',
        'Required Configuration',
        'Operational Impact',
        'Source Owner',
        'Required By',
        'Recommended Action',
        'Operational Domain Readiness',
        'Run Full Validation',
    )
    missing = [item for item in required if item not in content]
    assert not missing, f'Prometheus capability workspace is missing technical detail: {missing}'
    assert "for key in CAPABILITIES" in presentation
    assert "{'key': key, 'status': 'not_observed'}" in presentation
    assert 'for domain, required in _MODULE_REQUIREMENTS.items()' in presentation


def test_runtime_matches_alertmanager_health_and_history_contract() -> None:
    runtime = read(RUNTIME)
    panel = read(RUNTIME_PANEL)
    history = read(RUNTIME_HISTORY) + read(ROOT / 'app/templates/integrations/partials/_runtime_history.html')

    assert runtime.count('workspace_summary_card.render') == 3
    for value in ('Readiness Versus Health', 'How Monitoring Works', 'Resolver Correlation'):
        assert value in runtime
    for value in (
        'Runtime Health &amp; Diagnostics',
        'Refresh Runtime',
        'health_interpretation.render',
        'Diagnostic Pipeline',
        'Response Evidence',
        'Capability Context',
    ):
        assert value in panel
    for value in (
        'Recent Runtime Observations',
        'Manage Lifecycle',
        'Readiness:',
        'Capability Snapshot',
        'No State Change',
        'pagination_ui.numeric_pages',
    ):
        assert value in history


def test_scope_matches_alertmanager_binding_and_resolution_contract() -> None:
    scope = read(SCOPE)
    routes = read(ROUTES)
    service = read(SERVICE)

    required = (
        'Scope &amp; Resolution',
        'Scope Bindings',
        'Create Binding',
        'Effective Source Resolution',
        'Required Technical Capabilities',
        'Missing Technical Capabilities:',
        'Binding Coverage Missing:',
        'Pre-save Validation',
        'Instance Lifecycle &amp; Deletion',
        'data-prometheus-delete-button',
    )
    missing = [item for item in required if item not in scope]
    assert not missing, f'Prometheus scope workspace is incomplete: {missing}'
    assert 'hx-target="#prometheus-scope-workspace"' in scope
    assert 'role=role' in routes
    assert 'binding_role=role' not in routes
    assert "IntegrationInstance.provider_type == 'prometheus'" in service


def test_manage_workspace_uses_one_context_builder_for_full_and_partial_responses() -> None:
    routes = read(ROUTES)

    assert 'def _instance_detail_context(' in routes
    assert "context['delete_instance_url'] = _optional_endpoint_url(" in routes
    assert 'def _render_instance_partial(' in routes
    assert routes.count('_render_instance_partial(') >= 6
    assert 'ensure_canonical_instance(instance, provider_type=\'prometheus\')' in routes
    assert "@prometheus_bp.post('/instances/<int:instance_id>/runtime/refresh')" in routes


def test_form_labels_match_provider_manage_standard() -> None:
    forms = read(FORMS)

    assert "('none', 'No Authentication')" in forms
    assert "'Request Timeout'" in forms
    assert "'Verify TLS Certificate'" in forms
    assert "BooleanField('Allow KAORI to Use This Connection'" in forms


def test_standard_and_audit_document_parity_contract() -> None:
    standard = read(STANDARD)
    audit = read(AUDIT)

    for value in (
        'Four-tab contract',
        'Configuration is edited inside the manage workspace',
        'Validation & Capabilities contract',
        'Runtime & History contract',
        'Scope & Resolution contract',
        'legacy edit URL may redirect',
    ):
        assert value in standard
    for value in (
        'Separate configuration flow',
        'Incomplete capability presentation',
        'Runtime implementation drift',
        'Scope management drift',
        'Final parity contract',
    ):
        assert value in audit
