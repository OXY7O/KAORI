from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alertmanager_provider_core_is_consumer_neutral() -> None:
    registration = read('app/integrations/observability/alert_source/providers/alertmanager/__init__.py')
    validation = read('app/integrations/observability/alert_source/providers/alertmanager/validation.py')
    capabilities = read('app/integrations/observability/alert_source/providers/alertmanager/capabilities.py')
    capability_catalog = read(
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    )
    requirements = read('app/integrations/observability/alert_source/providers/alertmanager/requirements.py')

    assert 'CORE_CAPABILITY_KEYS' in registration
    assert "integration_provider_document('alertmanager')" in capabilities
    assert 'core_capability_keys:' in capability_catalog
    for key in ('status_v2', 'alerts_v2', 'silences_v2'):
        assert f'- {key}' in capability_catalog
    assert 'discover_payload_capabilities' not in validation
    assert 'Kubernetes' not in requirements
    assert 'MinIO' not in requirements
    assert 'status_v2' in requirements
    assert 'alerts_v2' in requirements
    assert 'silences_v2' in requirements


def test_alertmanager_consumer_profiles_are_asset_scoped() -> None:
    profiles = read('app/integrations/observability/alert_source/providers/alertmanager/binding_profiles.py')
    profile_catalog = read(
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    )
    binding_validation = read(
        'app/integrations/observability/alert_source/providers/alertmanager/binding_validation.py'
    )
    binding_management = read(
        'app/integrations/observability/alert_source/providers/alertmanager/binding_management.py'
    )

    assert "integration_provider_document('alertmanager')" in profiles
    assert 'profile_key: kubernetes-alerts-v1' in profile_catalog
    assert 'profile_key: object-storage-alerts-v1' in profile_catalog
    assert 'asset_type: object_storage_system' in profile_catalog
    assert 'get_alert_consumer_profile(binding.asset_type)' in binding_validation
    assert 'discover_payload_capabilities' in binding_validation
    assert 'binding.validation_profile' in binding_validation
    assert 'binding.validation_evidence' in binding_validation
    assert 'binding.validation_status' in binding_validation
    assert 'except AlertmanagerError as exc:' in binding_validation
    assert "binding.validation_status = 'ready'" in binding_validation
    assert "if binding.asset_type != 'global' and not alerts:" in binding_validation
    assert 'binding.validation_profile = consumer_profile.profile_key' in binding_management


def test_alertmanager_binding_evidence_drives_consumer_resolution() -> None:
    resolver = read('app/alert_sources/providers/alertmanager/resolver.py')
    evaluator = resolver.split('def _evaluate_binding', 1)[1].split('def _operational_rank', 1)[0]

    assert 'binding.validation_evidence or {}' in evaluator
    assert 'instance.capabilities or {}' not in evaluator
    assert "return binding.asset_type != 'global'" in resolver


def test_alertmanager_supports_object_storage_consumers_without_special_binding_table() -> None:
    forms = read('app/alert_sources/providers/alertmanager/forms.py')
    service = read('app/alert_sources/providers/alertmanager/service.py')
    routes = read('app/alert_sources/providers/alertmanager/routes.py')
    minio_service = read('app/object_storage/providers/minio/service.py')
    consumer_assets = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')

    assert 'registered_consumer_asset_definitions' in forms
    assert 'object_storage_scope_key' in forms
    assert 'integration_taxonomy_document()' in consumer_assets
    assert 'asset_type: object_storage_system' in taxonomy_catalog
    assert 'ObjectStorageSystem' in consumer_assets
    assert 'get_consumer_asset_definition' in service
    assert 'resolve_consumer_asset' in service
    assert 'binding_scope_validation_error' in routes
    assert 'create_source_binding(' not in minio_service
    assert 'minio_alertmanager' not in minio_service.lower()


def test_alertmanager_ui_exposes_consumer_profile_and_core_boundary() -> None:
    validation = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'
    )
    scope = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')

    assert 'Alertmanager Full Validation' in validation
    assert 'Alertmanager Provider Readiness' in validation
    assert (
        'Full Validation owns core APIs; bindings own consumer evidence; Runtime Refresh owns live health.'
        in validation
    )
    assert 'Consumer Binding Registry' in registry
    assert 'Consumer Profile' in registry
    assert 'Alert Identity Boundary' in scope
    assert 'Resolved Consumer Profile' in binding_modal


def test_alertmanager_consumer_profile_contract_is_documented() -> None:
    readme = read('app/integrations/observability/alert_source/providers/alertmanager/README.md')
    compatibility = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')

    assert 'kubernetes-alerts-v1' in readme
    assert 'object-storage-alerts-v1' in readme
    assert 'Provider Core Validation checks only provider-owned contracts' in readme
    assert 'Alert rules themselves are normally evaluated upstream by a metrics/rule engine' in readme
    assert 'Consumer alert contracts are binding-scoped.' in compatibility
    assert 'Alertmanager consumer-profile boundary' in module_map


def test_object_storage_alert_profile_direct_cutover_is_migration_guarded() -> None:
    profiles = read('app/integrations/observability/alert_source/providers/alertmanager/binding_profiles.py')
    profile_catalog = read(
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    )
    resolver = read('app/alert_sources/providers/alertmanager/resolver.py')
    migration = read('migrations/versions/20260814_object_storage_alert_profile.py')

    assert 'profile_key: object-storage-alerts-v1' in profile_catalog
    assert 'minio-alerts-v1' not in profile_catalog
    assert "integration_provider_document('alertmanager')" in profiles
    assert 'get_alert_consumer_profile' in resolver
    assert 'profile_eligible' in resolver
    assert 'Consumer validation profile' in resolver
    assert "validation_profile = 'object-storage-alerts-v1'" in migration
    assert "validation_profile = 'minio-alerts-v1'" in migration
    assert "validation_status = 'validation_required'" in migration
    assert "down_revision = '20260814_obj_forecast'" in migration
