from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_alertmanager_detail_uses_provider_v2_tabs_without_malformed_alpine_markup():
    content = read('app/templates/integrations/observability/alert_source/providers/alertmanager/instance_detail.html')
    assert 'Bindings & Consumers' in content
    assert 'x-data="integrationWorkspaceTabs(' in content
    assert 'x-on:popstate.window="syncTab()"' in content
    assert 'integration_workspace_tabs.js' in read('app/templates/layouts/app.html')
    assert "scrollIntoView({ behavior: 'smooth', block: 'start' })); } } }" not in content


def test_alertmanager_configuration_uses_read_only_contract_and_edit_link():
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_configuration.html'
    )
    shared = read('app/templates/integrations/components/_provider_configuration_contract.html')
    routes = read('app/integrations/observability/alert_source/providers/alertmanager/application/routes.py')
    assert 'provider_configuration_contract.render(' in content
    assert 'Alertmanager API Endpoint' in content
    assert 'Configure Connection' in shared
    assert 'data-kaori-provider-configuration-contract' in shared
    assert 'url_for("alertmanager.edit_instance"' in content
    assert "@alertmanager_bp.route('/instances/<int:instance_id>/edit'" in routes


def test_alertmanager_validation_uses_kubernetes_style_capability_readiness_and_registry():
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'
    )
    registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
    )
    assert 'Alertmanager Full Validation' in content
    assert 'Alertmanager Provider Readiness' in content
    assert 'integrations/components/_readiness_explanation.html' in content
    assert 'integrations/components/_capability_readiness.html' in content
    assert 'data-kaori-provider-capability-matrix' in content
    assert 'Validation Decision' not in content
    assert 'Capability Registry' in registry
    assert 'record_actions.view_more(' in registry
    assert 'table_ui.table_classes' in registry


def test_alertmanager_runtime_uses_kubernetes_layout_and_history_filters():
    panel = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html'
    )
    history = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_history.html'
    )
    assert 'integrations/components/_runtime_decision.html' in panel
    assert 'runtime_decision.render(' in panel
    assert 'Runtime Evidence' in panel
    assert 'data-kaori-alertmanager-runtime-evidence' in panel
    assert 'step.summary' in panel
    assert 'lg:sticky' not in panel
    assert 'xl:sticky' not in panel
    assert 'runtime_history_filters_enabled = true' in history


def test_alertmanager_bindings_use_standard_table_and_native_dialog():
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    assert 'Bindings &amp; Consumers' in content
    binding_registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    assert 'Consumer Binding Registry' in binding_registry
    assert 'Consumer Profile' in binding_registry
    assert 'Effective Consumer Resolution' in content
    assert 'Binding Decision' in content
    assert 'observability_binding_modal.render(' in content
    assert 'data-kaori-observability-binding-modal' in binding_modal
    assert '_binding_registry_layout.html' in binding_registry
    assert 'binding_registry_layout.table_classes()' in binding_registry


def test_alertmanager_runtime_history_accepts_server_side_filters():
    routes = read('app/integrations/observability/alert_source/providers/alertmanager/application/routes.py')
    presentation = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/presentation.py'
    )
    assert "history_trigger = request.args.get('history_trigger'" in routes
    assert "history_health = request.args.get('history_health'" in routes
    assert "history_readiness = request.args.get('history_readiness'" in routes
    assert "trigger_type: str = ''" in presentation
    assert "health_status: str = ''" in presentation
    assert "readiness: str = ''" in presentation


def test_alertmanager_connection_type_is_legacy_not_operator_configuration():
    form = read('app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html')
    card = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html'
    )
    content = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html'
    )
    presentation = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/presentation.py'
    )
    routes = read('app/integrations/routes.py')
    registration = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/registration_web.py'
    )

    assert '>Connection Type</label>' not in form
    assert '<select id="alertmanager-deployment-type"' not in form
    assert 'type="hidden"' in form
    assert 'name="deployment_type"' in form

    assert 'selected_deployment_type' not in card
    assert "'deployment_type'" not in card
    assert 'row.deployment_type' not in content
    assert "'deployment_type': selected_deployment_type" not in content
    assert "deployment_type: str = ''" not in presentation
    assert "'deployment_type': instance.deployment_type" not in presentation
    assert "deployment_type=request.args.get('deployment_type'" not in routes
    assert "deployment_type='cluster_managed'" not in registration


def test_observability_connection_copy_is_concise_and_binding_scoped():
    alertmanager = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'
    )
    metrics = read('app/templates/integrations/observability/metrics_source/instance_form.html')

    assert 'One Alertmanager serves multiple integrations.' in alertmanager
    assert 'Update metrics access while preserving validation and bindings.' in metrics
    assert 'Maintain governed validation and consumer-binding context.' not in metrics
    assert 'Update Alertmanager access while preserving consumer bindings.' in alertmanager
    assert 'Review Alertmanager readiness and bindings.' in alertmanager
    assert 'Maintain governed validation and consumer-binding context.' not in alertmanager


def test_alertmanager_review_copy_is_concise_and_explicit():
    detail_scope = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    validation = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'
    )
    configuration = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_configuration.html'
    )
    frontpage = read('app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html')
    binding_registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    alert_form = read('app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html')
    metrics_form = read('app/templates/integrations/observability/metrics_source/instance_form.html')

    assert 'Stable selectors isolate alert streams; changes require revalidation.' in detail_scope
    assert 'Review bindings, selectors, profiles, source resolution, and lifecycle guardrails.' in detail_scope
    assert 'Asset-specific alert contracts validate after binding.' in validation
    assert 'Required Alertmanager core contracts are missing.' in validation
    assert 'Defines whether KAORI verifies the source TLS certificate before trusted API access.' in configuration
    assert (
        'KAORI validates provider status, alert and silence API access, and compatibility evidence '
        'before the source is eligible for governed use.' in frontpage
    )
    assert 'Selector changes clear evidence and require revalidation.' in binding_registry
    assert 'Identity changes clear stale evidence and require revalidation.' in binding_modal
    assert 'How saved changes return to governed use.' in alert_form
    assert 'How saved changes return to governed use.' in metrics_form


def test_alertmanager_registration_guidance_is_compact_without_losing_gates() -> None:
    """The four human-marked hints are single-line desktop copy, not clipped UI."""

    from jinja2 import Environment

    form = read('app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html')
    Environment().parse(form)
    messages = (
        'Configure endpoint access, then test connectivity.',
        'Registration only; Full Validation gates use.',
        'One Alertmanager serves multiple integrations.',
        'Disabled connections stay stored, not resolved.',
    )
    for message in messages:
        assert form.count(message) == 1
        assert len(message) <= 50

    for obsolete in (
        'Define Alertmanager endpoint access and authentication, then verify reachability before registration.',
        'Registration creates the reusable connection identity only;',
        'One Alertmanager runtime can serve multiple integrations through',
        'Disabled connections stay stored but are excluded from scope resolution.',
    ):
        assert obsolete not in form

    # The detailed flow still owns the separately governed consumer gate.
    assert 'then complete Full Validation before attaching consumer bindings.' in form
    assert 'alertmanager_related_description ~' in form
    assert 'provider_registration_context.render(' in form
    assert 'connection_validation_header.render(' in form
    assert 'operational_toggle.render(' in form
    assert 'whitespace-nowrap' not in form
    assert 'line-clamp' not in form


def test_alertmanager_connection_registry_row_has_aligned_semantic_cells() -> None:
    """Keep full provider identity while displaying a compact binding count."""

    from jinja2 import Environment

    registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html'
    )
    Environment().parse(registry)
    populated = registry.split('{% for row in rows %}', 1)[1].split('{% else %}', 1)[0]
    cells = populated.split('<td class="{{ table_ui.cell_classes')
    assert len(cells) == 7  # Six populated cells, including titled Bindings and Actions.
    assert populated.count('align-top') == 6

    identity, endpoint, readiness, compatibility, bindings, actions = cells[1:]
    assert '{{ row.instance.name }}' in identity
    assert "{{ row.instance.description or 'Reusable alert source' }}" in identity
    assert 'truncate' not in identity
    assert '[overflow-wrap:anywhere]' in identity
    assert '{{ row.endpoint }}' in endpoint
    assert 'Alertmanager API v2' in endpoint
    assert '[overflow-wrap:anywhere]' in endpoint
    assert 'integration_status(row.readiness, display="indicator")' in readiness
    assert 'integration_status(row.compatibility, display="indicator")' in compatibility
    assert '{{ row.profile or "Capability profile pending" }}' in compatibility
    assert '{{ row.version or "Version not detected" }}' in compatibility

    assert "table_label.metadata_label(table_label.count_text(row.binding_count, 'Binding') )" in bindings
    assert "scope_labels|join(', ') if scope_labels else 'No scope bindings'" in bindings
    assert 'scope_labels|join(", ") if scope_labels else' in bindings
    assert 'Bound scope types:' in bindings
    assert 'truncate' not in bindings
    assert 'scope_labels.append(scope_type_labels.get(' in populated
    assert 'row.scope_types or []' in populated
    assert "url_for('alertmanager.instance_detail', instance_id=row.instance.id)" in actions
    assert '<td class="{{ table_ui.cell_classes(action=true) }} align-top">' in populated
    assert 'provider_registry.connection_registry_colgroup()' in registry
    assert 'provider_registry.connection_registry_head()' in registry
    assert 'provider_registry.pagination_footer(pagination,' in registry


def test_observability_edit_guidance_is_one_line_copy_with_full_validation_gate() -> None:
    """Shared edit flows stay concise without changing provider authority."""

    from jinja2 import Environment

    metrics = read('app/templates/integrations/observability/metrics_source/instance_form.html')
    alertmanager = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'
    )
    for form in (metrics, alertmanager):
        Environment().parse(form)
        assert 'flow_note="Saved changes require successful Full Validation."' in form
        assert 'Saving changes does not establish readiness until Full Validation succeeds.' not in form
        assert 'return readiness to Validation Required.' in form
        assert 'provider_registration_context.render(' in form

    assert '"Review " ~ metrics_source_label ~ " readiness and bindings."' in metrics
    assert '"Review Alertmanager readiness and bindings."' in alertmanager
    assert 'coverage, connection readiness, and consumer bindings from the observability workspace.' not in metrics
    assert 'Review Alertmanager coverage, readiness, and alert consumer bindings.' not in alertmanager

    catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    thanos = catalog.split('- key: thanos', 1)[1].split('\n- key:', 1)[0]
    assert 'description: PromQL queries with long-term retention.' in thanos
    assert 'adapter_key: prometheus_http' in thanos
    assert 'query_language: promql' in thanos
    assert 'default_query_horizon: historical' in thanos
    assert 'Thanos Query endpoint using the Prometheus HTTP API' not in thanos
    assert '{{ provider.description }}' in metrics
