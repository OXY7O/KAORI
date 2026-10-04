from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


DETAILS = {
    'kubernetes': 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html',
    'metrics_source': 'app/templates/integrations/observability/metrics_source/instance_detail.html',
    'alertmanager': 'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_detail.html',
    'minio': 'app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html',
    'harbor': 'app/templates/integrations/registry/providers/harbor/instance_detail.html',
}

VALIDATION = {
    'kubernetes': 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
    'metrics_source': 'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html',
    'alertmanager': 'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html',
    'minio': 'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html',
    'harbor': 'app/templates/integrations/registry/providers/harbor/partials/_detail_validation.html',
}

RUNTIME = {
    'kubernetes': 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
    'metrics_source': 'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html',
    'alertmanager': 'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html',
    'minio': 'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html',
    'harbor': 'app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html',
}


def test_provider_detail_lifecycle_labels_match_locked_standard() -> None:
    details = {provider: read(path) for provider, path in DETAILS.items()}

    for provider, source in details.items():
        assert 'Configuration' in source, provider
        assert 'Validation & Capabilities' in source, provider
        assert 'Runtime & History' in source, provider
        assert 'Produced by Full Validation' in source, provider
        assert 'Validated Capabilities' in source, provider

    for provider in ('kubernetes', 'minio', 'harbor'):
        assert 'Inventory & Lifecycle' in details[provider], provider

    for provider in ('metrics_source', 'alertmanager'):
        assert 'Bindings & Consumers' in details[provider], provider


def test_all_provider_validation_workspaces_share_full_validation_lifecycle() -> None:
    for provider, path in VALIDATION.items():
        source = read(path)
        assert 'connection_validation_header.render(' in source, provider
        assert 'capability_readiness.render(' in source, provider
        assert 'validation_poller.render(' in source, provider
        assert 'Run Full Validation' in source, provider
        assert 'Runtime Refresh' in source, provider


def test_all_provider_runtime_workspaces_preserve_refresh_separation() -> None:
    runtime = {provider: read(path) for provider, path in RUNTIME.items()}

    for provider, source in runtime.items():
        assert 'connection_validation_header.render(' in source, provider
        assert 'validation_poller.render(' in source, provider
        assert 'Runtime Refresh' in source, provider
        assert 'Full Validation' in source, provider

    for provider in ('metrics_source', 'alertmanager', 'minio', 'harbor'):
        assert 'runtime_decision.render(' in runtime[provider], provider

    assert 'Primary Finding' in runtime['kubernetes']
    assert 'Full Validation readiness remains independently evaluated.' in runtime['kubernetes']


def test_asset_owner_lifecycle_uses_shared_read_only_observability_registry() -> None:
    kubernetes = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_inventory_lifecycle.html'
    )
    kubernetes_registry = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_binding_registry.html'
    )
    minio = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html'
    )
    minio_registry = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_binding_registry.html'
    )
    harbor = read(
        'app/templates/integrations/registry/providers/harbor/partials/_detail_scope.html'
    )
    harbor_registry = read(
        'app/templates/integrations/registry/providers/harbor/partials/_binding_registry.html'
    )

    for provider, scope in (
        ('kubernetes', kubernetes),
        ('minio', minio),
        ('harbor', harbor),
    ):
        assert 'Inventory &amp; Lifecycle' in scope, provider
        assert 'read-only for binding' in scope, provider
        assert 'Open Observability' in scope, provider

    for provider, registry in (
        ('kubernetes', kubernetes_registry),
        ('minio', minio_registry),
        ('harbor', harbor_registry),
    ):
        assert 'integrations/components/_asset_owner_observability_sources.html' in registry, provider
        assert 'Bound Observability Sources' in registry, provider
        assert 'components/pagination.html' in registry, provider
        assert 'components/loading_bar.html' in registry, provider
        assert 'data-kaori-auto-submit' in registry, provider
        assert 'binding_page' in registry, provider
        assert 'binding_per_page' in registry, provider


def test_kubernetes_bound_source_registry_is_paginated_server_side() -> None:
    service = read('app/integrations/service.py')
    routes = read('app/integrations/routes.py')
    registry = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_binding_registry.html'
    )

    assert 'binding_page: int = 1' in service
    assert 'binding_per_page: int = 5' in service
    assert 'source_bindings, source_binding_pagination = _paginate(' in service
    assert "'source_binding_total': len(all_source_bindings)" in service
    assert "'source_binding_pagination': source_binding_pagination" in service
    assert "@integrations_bp.get('/kubernetes/<string:cluster_id>/bindings/registry')" in routes
    assert 'def kubernetes_binding_registry(' in routes
    assert "request.args.get('binding_page', 1, type=int)" in routes
    assert "request.args.get('binding_per_page', 5, type=int)" in routes
    assert 'hx-target="#kubernetes-binding-registry"' in registry
    assert 'pagination_ui.numeric_pages(' in registry
    assert 'source_binding_pagination.allowed_per_page' in registry
