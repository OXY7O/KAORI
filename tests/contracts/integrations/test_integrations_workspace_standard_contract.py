from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def exists(relative: str) -> bool:
    return (ROOT / relative).exists()


def test_integrations_uses_one_semantic_status_owner() -> None:
    adapter = read('app/templates/integrations/components/_semantic_status.html')
    global_labels = read('app/templates/components/table_label.html')

    assert not exists('app/templates/integrations/partials/_status_badge.html')
    assert 'components/table_label.html' in adapter
    assert 'table_label.status_label(' in adapter
    assert 'compatible_with_warnings' in global_labels
    assert 'capability_mismatch' in global_labels
    assert 'legacy_fallback' in global_labels
    assert 'not_observed' in global_labels


def test_provider_registries_share_geometry_loading_and_pagination() -> None:
    shared = read('app/templates/integrations/components/_provider_registry.html')
    metrics_source = read('app/templates/integrations/observability/metrics_source/partials/_instance_inventory.html')
    alertmanager = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html'
    )
    metrics_source_results = read(
        'app/templates/integrations/observability/metrics_source/partials/_inventory_content.html'
    )
    alertmanager_results = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html'
    )

    for token in ('registry_header', 'search_field', 'select_field', 'pagination_footer'):
        assert f'macro {token}' in shared
    assert 'components/loading_bar.html' in shared
    assert 'hx-push-url="true"' in shared
    assert 'href_endpoint=endpoint' in shared

    for template in (metrics_source, alertmanager):
        assert 'integrations/components/_provider_registry.html' in template
        assert 'provider_registry.registry_header(' in template
        assert 'provider_registry.search_field(' in template
        assert 'provider_registry.select_field(' in template

    assert 'deployment_type' in alertmanager
    assert 'provider_registry.pagination_footer(' in metrics_source_results
    assert 'provider_registry.pagination_footer(' in alertmanager_results
    kubernetes = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html'
    )
    coverage = read('app/templates/components/integration_coverage.html')
    assert 'provider_registry.registry_header(' in kubernetes
    assert 'provider_registry.registry_header(' in coverage


def test_runtime_overview_uses_bright_evidence_and_shared_controls() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')

    assert 'integrations/components/_workspace.html' in runtime
    assert 'integration_ui.metric_grid_classes(' in runtime
    assert 'integration_ui.metric_card(' in runtime
    assert 'table_ui.inventory_filter_bar_classes()' in runtime
    assert 'table_ui.filter_select_classes()' in runtime
    assert 'provider_registry.pagination_footer(' in runtime
    assert 'components/loading_bar.html' in runtime


def test_runtime_history_has_one_direct_shared_component() -> None:
    routes = read('app/integrations/routes.py')
    shared = read('app/templates/integrations/partials/_runtime_history.html')

    assert not exists(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_history.html'
    )
    assert "'integrations/partials/_runtime_history.html'" in routes
    assert 'integrations/components/_semantic_status.html' in shared
    assert 'runtime_history_detail_endpoint_name' in shared
    assert 'runtime_history_route_args_value' in shared
    assert "'integrations.kubernetes_detail'" not in shared
    assert 'endpoint=runtime_history_endpoint_name' in shared


def test_dead_binding_presentation_is_removed() -> None:
    assert not exists('app/templates/integrations/partials/_binding_validation_posture.html')


def test_integrations_templates_do_not_reintroduce_micro_typography() -> None:
    roots = (
        ROOT / 'app/templates/integrations',
        ROOT / 'app/templates/integrations/observability/metrics_source',
        ROOT / 'app/templates/integrations/observability/alert_source/providers/alertmanager',
    )
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob('*.html'):
            source = path.read_text(encoding='utf-8')
            if 'text-[10px]' in source or 'text-[11px]' in source or 'tracking-[' in source:
                offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_integrations_does_not_add_inline_submit_handlers() -> None:
    roots = (
        ROOT / 'app/templates/integrations',
        ROOT / 'app/templates/integrations/observability/metrics_source',
        ROOT / 'app/templates/integrations/observability/alert_source/providers/alertmanager',
    )
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob('*.html'):
            source = path.read_text(encoding='utf-8')
            if 'onchange=' in source or 'onclick=' in source or 'onsubmit=' in source:
                offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_integrations_standard_is_implemented_not_draft() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    app_readme = read('app/integrations/README.md')

    assert 'Status: Locked canonical baseline' in standard
    assert 'KAORI Integrations Lock v1' in standard
    assert 'Provider-local presentation wrappers are prohibited' in standard
    assert 'Technical matrices may use horizontal scrolling only' in standard
    assert 'Both documents are audit-only' not in app_readme
