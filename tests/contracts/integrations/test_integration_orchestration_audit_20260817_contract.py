from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_domain_workspace_is_htmx_partial_and_demand_loads_selected_registry() -> None:
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/domain_service.py')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    page = read('app/templates/integrations/domain.html')

    assert "is_workspace_partial = is_htmx_request() and htmx_target() == 'domain-workspace'" in routes
    assert 'include_capabilities=not is_workspace_partial' in routes
    assert "return render_template('integrations/partials/_domain_workspace.html', **context)" in routes
    assert "if normalized_tab == 'registry':" in service
    assert 'all_provider_rows = _provider_registry_rows(' in service
    assert 'all_binding_rows = _binding_registry_rows(' in service
    assert "include_details=normalized_tab == 'bindings'" in service
    assert 'load_only(' in service
    assert "'provider_registry_pagination': provider_pagination" in service
    assert "'binding_registry_pagination': binding_pagination" in service
    assert '{% include "integrations/partials/_domain_workspace.html" %}' in page
    assert 'id="domain-workspace"' in workspace


def test_orchestration_domain_counts_only_consumer_bindings_and_disabled_targets_need_review() -> None:
    service = read('app/integrations/domain_service.py')

    assert 'consumer_bindings = [binding for binding in related_bindings if not _is_owner_asset_binding(binding)]' in service
    assert "'bindings': sum(1 for binding in consumer_bindings if binding.enabled)" in service
    assert '_capability_rows(domain.key, modules, provider_types, consumer_bindings)' in service
    assert "if registered <= 0:" in service
    assert "if enabled <= 0:" in service
    assert "return 'attention'" in service
    assert 'attention = len(targets) - ready' in service


def test_domain_registries_follow_kaori_filter_and_clear_filter_standard() -> None:
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/domain_service.py')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    for token in (
        "query=request.args.get('provider_q', '').strip()",
        "provider_type=request.args.get('provider_type', '').strip()",
        "readiness=request.args.get('provider_readiness', '').strip()",
        "query=request.args.get('binding_q', '').strip()",
        "provider=request.args.get('binding_provider', '').strip()",
        "status=request.args.get('binding_status', '').strip()",
    ):
        assert token in routes

    assert 'def _filter_provider_rows(' in service
    assert 'def _filter_binding_rows(' in service
    assert "normalized_query in row['search_text']" in service
    assert "row['source_provider_type'] == provider" in service
    assert "row['validation_status'] == status" in service

    assert 'components/table_registry.html' in workspace
    assert workspace.count('registry_ui.filter_form(') == 2
    assert workspace.count('registry_ui.clear_filters_link(') == 2
    assert "page_param='provider_page'" in workspace
    assert "per_page_param='provider_per_page'" in workspace
    assert "page_param='binding_page'" in workspace
    assert "per_page_param='binding_per_page'" in workspace
    assert "empty_state_label = 'No Results'" in workspace
    assert 'No {{ domain.label }} Consumer Bindings Yet' in workspace
    assert 'Use Add Consumer Binding' not in workspace


def test_domain_instance_loading_does_not_preload_unused_binding_relationship() -> None:
    service = read('app/integrations/domain_service.py')
    loader = service.split('def _load_domain_instances(', 1)[1].split('def _load_related_bindings(', 1)[0]

    assert 'IntegrationInstance.query.filter(IntegrationInstance.provider_type.in_(provider_types))' in loader
    assert 'selectinload(IntegrationInstance.bindings)' not in loader
    assert 'detail_url_for_record' in read('app/integrations/registry.py')
    assert '_resolve_provider_detail_urls(provider_registry_rows)' in service
    assert '_resolve_binding_detail_urls(binding_registry_rows)' in service
