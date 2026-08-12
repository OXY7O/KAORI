from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_minio_persistence_uses_provider_neutral_object_storage_asset() -> None:
    asset = read('app/models/object_storage.py')
    model = read('app/models/minio.py')
    integration = read('app/models/integration.py')
    migration = read('migrations/versions/20260812_minio_object_storage_provider.py')

    assert "__tablename__ = 'object_storage_systems'" in asset
    assert "__tablename__ = 'minio_instances'" in model
    assert 'integration_instance_id' in model
    assert 'object_storage_system_id' in model
    assert 'EncryptedText()' in model
    assert 'minio_record' in integration
    assert "down_revision = '20260810_retire_welcome_view'" in migration
    assert "'object_storage_systems'" in migration
    assert "'minio_instances'" in migration
    assert 'minio_prometheus' not in migration.lower()
    assert 'prometheus_id' not in model


def test_minio_registry_contract_is_storage_object_storage() -> None:
    registration = read('app/integrations/minio/__init__.py')
    registry = read('app/integrations/registry.py')
    compatibility = read('app/integrations/minio/compatibility.py')
    capabilities = read('app/integrations/minio/capabilities.py')

    assert "'app.integrations.minio'" in registry
    assert "provider_type='minio'" in registration
    assert "domain_key='storage'" in registration
    assert "capability_key='object_storage'" in registration
    assert "workspace_endpoint='minio.index'" in registration
    assert "navigation_endpoint_prefixes=('minio.',)" in registration
    assert "SUPPORTED_RELEASE = 'RELEASE.2024-08-03T04-33-23Z'" in compatibility
    assert "PROFILE_KEY = 'minio-release-2024-08-03'" in compatibility
    assert "CAPABILITY_PROFILE = 'minio-object-storage-api-v1'" in capabilities


def test_minio_api_plane_uses_s3_sdk_and_encrypted_credentials() -> None:
    client = read('app/integrations/minio/client.py')
    forms = read('app/minio/forms.py')
    model = read('app/models/minio.py')

    assert "boto3.client(\n        's3'" in client
    assert "signature_version='s3v4'" in client
    assert "s3={'addressing_style': addressing_style or 'path'}" in client
    assert 'client.list_buckets()' in client
    assert "PasswordField('Secret Key'" in forms
    assert "StringField('Access Key'" in forms
    assert 'secret_key: Mapped[str] = mapped_column(EncryptedText()' in model


def test_minio_prometheus_metrics_plane_reuses_canonical_asset_binding() -> None:
    service = read('app/minio/service.py')
    registration = read('app/integrations/minio/__init__.py')
    binding_service = read('app/integrations/binding_service.py')

    assert "create_source_binding(\n        'prometheus'" in service
    assert 'asset_type=OBJECT_STORAGE_SYSTEM_SCOPE' in service
    assert 'asset_key=instance.object_storage_system_id' in service
    assert 'capability_scope=list(PROMETHEUS_CAPABILITY_SCOPE)' in service
    assert 'def create_source_binding(' in binding_service
    assert 'minio_prometheus' not in service.lower()

    assert 'BindingValidationProfile(' in registration
    assert 'asset_type=OBJECT_STORAGE_SYSTEM_SCOPE' in registration
    assert "BindingProbe('minio_software_version_info'" in registration
    assert "BindingProbe('minio_cluster_usage_total_bytes'" in registration
    assert "BindingProbe('minio_bucket_usage_total_bytes'" in registration


def test_validation_admission_and_runtime_monitoring_are_provider_generic() -> None:
    validation_web = read('app/integrations/validation/web.py')
    monitoring = read('app/integrations/runtime/monitoring.py')

    assert 'get_integration(provider_type).get_instance(instance_id)' in validation_web
    assert 'model_by_provider' not in validation_web
    assert 'PrometheusInstance' not in validation_web
    assert 'AlertmanagerInstance' not in validation_web
    assert 'KubernetesConnection' not in validation_web

    assert 'IntegrationInstance.query.filter(' in monitoring
    assert 'get_integration(identity.provider_type)' in monitoring
    assert 'module.get_record_for_canonical(identity.id)' in monitoring
    for provider_model in ('PrometheusInstance', 'AlertmanagerInstance', 'KubernetesConnection', 'MinioInstance'):
        assert provider_model not in monitoring


def test_minio_workspace_is_nested_under_integrations_storage() -> None:
    blueprints = read('app/bootstrap/blueprints.py')
    navigation = read('app/common/navigation.py')
    integration_navigation = read('app/integrations/navigation.py')
    presentation = read('app/bootstrap/presentation.py')
    routes = read('app/minio/routes.py')
    index = read('app/templates/minio/index.html')
    tabs = read('app/templates/components/integration_workspace_tabs.html')
    detail = read('app/templates/minio/instance_detail.html')

    assert 'from app.minio.routes import minio_bp' in blueprints
    assert '        minio_bp,' in blueprints
    assert "Blueprint('minio', __name__, url_prefix='/integrations/minio')" in routes
    assert 'integration_endpoint_owner(request.endpoint)' in presentation
    assert 'integration_owner=integration_owner' in presentation
    assert 'integration_owner: Mapping[str, str] | None = None' in navigation
    assert 'def integration_endpoint_owner(' in integration_navigation
    assert "'domain_label': module.domain.label" in integration_navigation
    assert 'MinIO Integrations' in index
    assert 'Register Connection' in index
    assert 'Integration Coverage' in tabs
    assert 'Connection Registry' in tabs
    assert 'framed_workspace_tabs.render' in detail
    assert 'Core Validation' in detail
    assert 'Bindings & Consumers' in detail


def test_minio_service_boundary_uses_input_contracts_not_forms() -> None:
    service = read('app/minio/service.py')
    registration = read('app/minio/registration.py')
    forms = read('app/minio/forms.py')

    assert 'MinioRegistrationInput' in service
    assert 'MinioMetricsBindingInput' in service
    assert 'MinioAlertBindingInput' in service
    assert 'from app.minio.contracts import MinioRegistrationInput' in registration
    assert 'app.minio.forms' not in service
    assert 'app.minio.forms' not in registration
    assert 'def to_input(self) -> MinioRegistrationInput:' in forms
    assert 'def to_input(self) -> MinioMetricsBindingInput:' in forms
    assert 'def to_input(self) -> MinioAlertBindingInput:' in forms


def test_domain_section_header_runtime_regression_is_closed() -> None:
    template = read('app/templates/integrations/domain.html')

    assert '{% call integration_ui.section_header(' not in template
    assert '{{ integration_ui.section_header(' in template
