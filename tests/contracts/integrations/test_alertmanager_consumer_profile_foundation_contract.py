from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alertmanager_provider_core_is_consumer_neutral() -> None:
    registration = read('app/integrations/alertmanager/__init__.py')
    validation = read('app/integrations/alertmanager/validation.py')
    capabilities = read('app/integrations/alertmanager/capabilities.py')
    requirements = read('app/integrations/alertmanager/requirements.py')

    assert 'CORE_CAPABILITY_KEYS' in registration
    assert "CORE_CAPABILITY_KEYS = ('status_v2', 'alerts_v2', 'silences_v2')" in capabilities
    assert 'discover_payload_capabilities' not in validation
    assert 'Kubernetes' not in requirements
    assert 'MinIO' not in requirements
    assert 'status_v2' in requirements
    assert 'alerts_v2' in requirements
    assert 'silences_v2' in requirements


def test_alertmanager_consumer_profiles_are_asset_scoped() -> None:
    profiles = read('app/integrations/alertmanager/binding_profiles.py')
    binding_validation = read('app/integrations/alertmanager/binding_validation.py')
    binding_management = read('app/integrations/alertmanager/binding_management.py')

    assert "profile_key='kubernetes-alerts-v1'" in profiles
    assert "profile_key='minio-alerts-v1'" in profiles
    assert "asset_type='object_storage_system'" in profiles
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
    resolver = read('app/alertmanager/resolver.py')
    evaluator = resolver.split('def _evaluate_binding', 1)[1].split('def _operational_rank', 1)[0]

    assert 'binding.validation_evidence or {}' in evaluator
    assert 'instance.capabilities or {}' not in evaluator
    assert "return binding.asset_type != 'global'" in resolver


def test_alertmanager_supports_object_storage_consumers_without_special_binding_table() -> None:
    forms = read('app/alertmanager/forms.py')
    service = read('app/alertmanager/service.py')
    routes = read('app/alertmanager/routes.py')
    minio_service = read('app/minio/service.py')

    assert "'object_storage_system'" in forms
    assert 'object_storage_scope_key' in forms
    assert 'ObjectStorageSystem' in service
    assert 'binding_scope_validation_error' in routes
    assert "scope_type == 'object_storage_system'" in service
    assert "create_source_binding(\n        'alertmanager'" in minio_service
    assert 'asset_type=OBJECT_STORAGE_SYSTEM_SCOPE' in minio_service
    assert 'minio_alertmanager' not in minio_service.lower()


def test_alertmanager_ui_exposes_consumer_profile_and_core_boundary() -> None:
    validation = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    scope = read('app/templates/alertmanager/partials/_detail_scope.html')

    assert 'Alertmanager Core Validation' in validation
    assert 'Alertmanager Provider Readiness' in validation
    assert 'Consumer Validation Boundary' in validation
    assert 'Consumer Binding Registry' in scope
    assert 'Consumer Profile' in scope
    assert 'object_storage_scope_key' in scope
    assert 'Resolved Consumer Profile' in scope


def test_alertmanager_consumer_profile_contract_is_documented() -> None:
    readme = read('app/integrations/alertmanager/README.md')
    compatibility = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')

    assert 'kubernetes-alerts-v1' in readme
    assert 'minio-alerts-v1' in readme
    assert 'Provider Core Validation checks only provider-owned contracts' in readme
    assert 'Alert rules themselves are normally evaluated upstream by Prometheus' in readme
    assert 'Consumer alert contracts are binding-scoped.' in compatibility
    assert 'Alertmanager consumer-profile boundary' in module_map
