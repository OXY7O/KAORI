from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_observability_binding_assets_are_registered_once_and_extensible() -> None:
    registry = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    coverage = read('app/integrations/coverage.py')

    for marker in (
        'registered_consumer_asset_definitions()',
        'build_consumer_asset_groups(',
        'A new managed asset (for example Vault) becomes bindable',
        'do not need a new product-specific binding form',
        'integration_taxonomy_document()',
    ):
        assert marker in registry
    assert 'asset_type: kubernetes_cluster' in taxonomy_catalog
    assert 'asset_type: object_storage_system' in taxonomy_catalog

    assert 'registered_consumer_asset_definitions' in coverage
    assert "'scope_type': definition.asset_type" in coverage
    assert 'ObjectStorageSystem.query' not in coverage


def test_metrics_source_and_alertmanager_own_binding_mutation_through_one_shared_modal() -> None:
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    prom_scope = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    alert_scope = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    prom_routes = read('app/integrations/observability/metrics_source/application/routes.py')
    prom_binding_web = read('app/integrations/observability/metrics_source/application/binding_web.py')
    alert_forms = read('app/integrations/observability/alert_source/providers/alertmanager/application/forms.py')

    assert 'data-kaori-observability-binding-modal' in modal
    assert 'Consumer Type' in modal
    assert 'Resolved Consumer Profile' in modal
    assert 'Create Binding' in modal

    for source in (prom_scope, alert_scope):
        assert 'Add Binding' in source
        assert '_observability_binding_modal.html' in source
        assert 'observability_binding_modal.render(' in source
        assert 'Add Kubernetes Binding' not in source
        assert 'Add MinIO Binding' not in source

    assert "request.form.get('asset_type'" in prom_binding_web
    assert 'binding_web.add_instance_binding(instance_id)' in prom_routes
    assert "request.form.get('asset_key'" in prom_binding_web
    assert 'SUPPORTED_SCOPE_TYPES = {' in alert_forms
    assert 'registered_consumer_asset_definitions()' in alert_forms


def test_asset_owner_pages_inventory_bound_sources_without_owning_binding_mutation() -> None:
    shared_inventory = read('app/templates/integrations/components/_asset_owner_observability_sources.html')
    kubernetes_lifecycle = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_inventory_lifecycle.html'
    )
    minio_lifecycle = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html'
    )
    minio_binding_registry = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_binding_registry.html'
    )
    minio_routes = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')
    minio_forms = read('app/integrations/storage/object_storage/providers/minio/application/forms.py')
    minio_service = read('app/integrations/storage/object_storage/providers/minio/application/service.py')

    for marker in ('Source', 'Source Readiness', 'Binding Validation', 'Effective Resolution'):
        assert marker in shared_inventory

    assert '_asset_owner_observability_sources.html' in kubernetes_lifecycle
    assert 'asset_owner_sources.render(' in kubernetes_lifecycle
    assert '_asset_owner_observability_sources.html' in minio_binding_registry
    assert 'asset_owner_sources.render(' in minio_binding_registry
    assert 'integrations/storage/object_storage/providers/minio/partials/_binding_registry.html' in minio_lifecycle

    assert 'Inventory & Lifecycle' in read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html'
    )
    assert 'Inventory & Lifecycle' in read(
        'app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html'
    )
    assert 'Open Observability' in minio_lifecycle

    for retired_owner_mutation in (
        'def create_metrics_binding',
        'def create_alert_binding',
        'def validate_binding',
        'def remove_binding',
    ):
        assert retired_owner_mutation not in minio_routes

    assert 'MinioMetricsBindingForm' not in minio_forms
    assert 'MinioAlertBindingForm' not in minio_forms
    assert 'create_source_binding(' not in minio_service


def test_provider_configuration_and_readiness_use_shared_kaori_surfaces() -> None:
    configuration = read('app/templates/integrations/components/_provider_configuration_contract.html')
    operational_context = read('app/templates/integrations/components/_provider_operational_context.html')
    readiness = read('app/templates/integrations/components/_readiness_explanation.html')
    prom_capabilities = read(
        'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
    )
    alert_capabilities = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
    )

    assert 'operational_context.render(' in configuration
    assert 'Operational Boundary' not in configuration
    assert 'Operational Flow' not in configuration
    assert 'data-kaori-provider-operational-context' in operational_context
    assert 'Authority Boundary' in operational_context

    assert 'data-kaori-readiness-explanation' in readiness
    assert 'data-kaori-consumer-readiness-boundary' in readiness
    assert 'Why Readiness' not in readiness  # title is caller/state-owned, geometry is shared.

    for registry in (prom_capabilities, alert_capabilities):
        assert 'Capability Registry' in registry
        assert 'View More' in registry
        assert 'components/pagination.html' in registry
        assert 'Search Capability' in registry
        assert 'Validation Status' in registry


def test_workspace_standard_locks_source_owned_observability_binding_and_future_assets() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    module_map = read('docs/architecture/integration-module-map.md')
    integrations_readme = read('app/integrations/README.md')

    for marker in (
        'binding mutation is source-owned',
        'shared `Add Binding` modal',
        'Inventory & Lifecycle',
        'Future managed assets such as Vault',
        'vault-metrics-v1',
        'vault-alerts-v1',
    ):
        assert marker in standard

    assert 'consumer_assets.py' in module_map
    assert 'Vault' in module_map
    assert 'Metrics Source/Alertmanager own binding creation, validation, update, and' in module_map
    assert 'removal from their `Bindings & Consumers` workspaces.' in module_map

    assert 'consumer-source relationships only' in integrations_readme
    assert 'Metrics Source and Alertmanager own binding mutation' in integrations_readme


def test_binding_actions_keep_canonical_single_line_geometry() -> None:
    coverage = read('app/templates/components/integration_coverage_content.html')
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')

    assert 'whitespace-nowrap px-5 py-4 text-right sm:px-6' in coverage
    assert 'shrink-0 items-center gap-1.5 whitespace-nowrap' in coverage
    assert 'Manage Binding' in coverage
    assert 'Choose Source' in coverage

    assert 'min-w-0 flex-1 text-xs leading-5 text-content-muted' in modal
    assert 'flex shrink-0 items-center justify-end gap-2' in modal
    assert 'shrink-0 items-center justify-center whitespace-nowrap' in modal
    assert 'gap-2 whitespace-nowrap rounded-lg bg-kaori-primary' in modal
