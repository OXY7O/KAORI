#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTHON_FILES = (
    'app/models/object_storage.py',
    'app/models/minio.py',
    'app/integrations/storage/object_storage/providers/minio/__init__.py',
    'app/integrations/storage/object_storage/providers/minio/adapter.py',
    'app/integrations/storage/object_storage/providers/minio/capabilities.py',
    'app/integrations/storage/object_storage/providers/minio/client.py',
    'app/integrations/storage/object_storage/providers/minio/compatibility.py',
    'app/integrations/observability/metrics_source/binding_profiles.py',
    'app/integrations/observability/metrics_source/binding_validators/object_storage.py',
    'app/integrations/storage/object_storage/providers/minio/application/contracts.py',
    'app/integrations/storage/object_storage/providers/minio/application/forms.py',
    'app/integrations/storage/object_storage/providers/minio/application/presentation.py',
    'app/integrations/storage/object_storage/providers/minio/application/registration.py',
    'app/integrations/storage/object_storage/providers/minio/application/routes.py',
    'app/integrations/storage/object_storage/providers/minio/application/service.py',
    'app/integrations/storage/object_storage/providers/minio/application/workspace_web.py',
    'migrations/versions/20260812_minio_object_storage_provider.py',
    'migrations/versions/20260812_remove_minio_owner_self_binding.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f'FAIL: {message}')


def main() -> None:
    for relative in PYTHON_FILES:
        source = read(relative)
        ast.parse(source, filename=relative)

    object_storage = read('app/models/object_storage.py')
    minio_model = read('app/models/minio.py')
    migration = read('migrations/versions/20260812_minio_object_storage_provider.py')
    owner_binding_cleanup = read('migrations/versions/20260812_remove_minio_owner_self_binding.py')
    registration = read('app/integrations/storage/object_storage/providers/minio/__init__.py')
    metrics_catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    object_storage_validator = read(
        'app/integrations/observability/metrics_source/binding_validators/object_storage.py'
    )
    compatibility = read('app/integrations/storage/object_storage/providers/minio/compatibility.py')
    provider_catalog = read('app/definitions/catalogs/integrations/storage/object_storage/contract.yaml')
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    service = read('app/integrations/storage/object_storage/providers/minio/application/service.py')
    registration_service = read('app/integrations/storage/object_storage/providers/minio/application/registration.py')
    validation_web = read('app/integrations/validation/web.py')
    monitoring = read('app/integrations/runtime/monitoring.py')
    blueprints = read('app/bootstrap/blueprints.py')
    breadcrumbs = read('app/common/navigation.py')
    integration_navigation = read('app/integrations/navigation.py')
    presentation = read('app/bootstrap/presentation.py')
    domain_template = read('app/templates/integrations/domain.html')
    minio_detail = read('app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html')
    minio_configuration = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html'
    )
    provider_configuration_contract = read(
        'app/templates/integrations/components/_provider_configuration_contract.html'
    )
    minio_scope = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html')
    minio_runtime = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html'
    )
    minio_validation = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
    )
    minio_capability_registry = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html'
    )
    minio_binding_registry = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_binding_registry.html'
    )
    minio_routes = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')
    deletion = read('app/integrations/deletion.py')

    require(
        "__tablename__ = 'object_storage_systems'" in object_storage, 'provider-neutral object storage asset missing'
    )
    require("__tablename__ = 'minio_instances'" in minio_model, 'MinIO provider model missing')
    require('integration_instance_id' in minio_model, 'MinIO must use canonical IntegrationInstance identity')
    require('object_storage_system_id' in minio_model, 'MinIO must own an ObjectStorageSystem asset')
    require('EncryptedText()' in minio_model, 'MinIO secret key must use canonical encrypted credential storage')

    require(
        "down_revision = '20260810_retire_welcome_view'" in migration,
        'MinIO migration must extend current migration head',
    )
    require("op.create_table(\n        'object_storage_systems'" in migration, 'object storage asset migration missing')
    require("op.create_table(\n        'minio_instances'" in migration, 'MinIO provider migration missing')
    require('minio_metrics' not in migration.lower(), 'MinIO must not add a provider-pair binding table')
    require(
        "down_revision = '20260812_prom_consumer_profiles'" in owner_binding_cleanup,
        'MinIO owner-binding cleanup must extend the consumer-profile head',
    )
    require('DELETE FROM integration_bindings' in owner_binding_cleanup, 'MinIO owner self-binding cleanup is missing')
    require("ii.provider_type = 'minio'" in owner_binding_cleanup, 'MinIO owner-binding cleanup must target MinIO only')

    require("provider_type='minio'" in registration, 'MinIO provider is not registered')
    require("domain_key='storage'" in registration, 'MinIO must belong to Storage')
    require("capability_key='object_storage'" in registration, 'MinIO must belong to Object Storage')
    require("navigation_endpoint_prefixes=('minio.',)" in registration, 'MinIO navigation ownership is missing')
    require("'binding.create'" not in registration, 'MinIO provider must not create a self consumer binding')
    require("'binding.validate'" not in registration, 'MinIO Core Validation must not validate an owner self-binding')
    require(
        'asset_type: object_storage_system' in metrics_catalog,
        'Object Storage Metrics Source consumer profile must be asset-scoped',
    )
    require(
        'profile_key: object-storage-metrics-v1' in metrics_catalog,
        'Object Storage Metrics Source consumer profile missing',
    )
    require(
        "asset_profile='minio-v2'" in object_storage_validator,
        'MinIO provider-qualified Metrics Source validation adapter missing',
    )
    require(
        'ObjectStorageMetricsProfileAuditor' in object_storage_validator,
        'MinIO Metrics Source readiness auditor missing',
    )
    require(
        'register_binding_validation_profile' not in registration,
        'MinIO provider must not own a Metrics Source consumer-profile registration',
    )
    require(
        'BindingProbe(' not in registration,
        'MinIO provider must not embed Metrics Source metric probes',
    )

    require(
        "integration_provider_document('object_storage')" in compatibility,
        'MinIO compatibility adapter must read the Definition Registry',
    )
    require(
        'minimum_release: RELEASE.2024-08-03T04-33-23Z' in provider_catalog,
        'supported MinIO release contract drifted',
    )
    require('key: minio-release-2024-08-03' in provider_catalog, 'MinIO compatibility profile missing')
    require(
        'capability_profile: minio-object-storage-api-v1' in provider_catalog,
        'MinIO API capability profile missing',
    )

    require("boto3.client(\n        's3'" in client, 'MinIO API client must use the existing S3 SDK boundary')
    require("signature_version='s3v4'" in client, 'MinIO S3 client must use SigV4')
    require('client.list_buckets()' in client, 'MinIO registration validation must prove bucket discovery access')

    require(
        'ensure_primary_asset_binding' not in service, 'MinIO registration must not create a provider-to-self binding'
    )
    require(
        not (ROOT / 'app/integrations/storage/object_storage/providers/minio/binding.py').exists(),
        'deprecated MinIO owner-binding module must be removed',
    )
    require('create_source_binding' not in service, 'MinIO asset-owner service must not mutate observability bindings')
    require('IntegrationBinding' not in minio_model, 'MinIO model must not own direct observability source bindings')
    require(
        'app.integrations.storage.object_storage.providers.minio.application.forms' not in service,
        'MinIO service layer must not depend on WTForms',
    )
    require(
        'app.integrations.storage.object_storage.providers.minio.application.forms' not in registration_service,
        'MinIO registration proof must not depend on WTForms',
    )
    require('MinioRegistrationInput' in service, 'MinIO service must consume the registration input contract')
    require(
        'MinioMetricsBindingInput' not in service,
        'MinIO asset-owner service must not own metrics binding input contracts',
    )
    require(
        'MinioAlertBindingInput' not in service, 'MinIO asset-owner service must not own alert binding input contracts'
    )

    require(
        'get_integration(provider_type).get_instance(instance_id)' in validation_web,
        'validation admission must be registry-driven',
    )
    for legacy in ('MetricsSource', 'AlertmanagerInstance', 'KubernetesConnection'):
        require(legacy not in validation_web, f'validation admission still hard-codes {legacy}')

    require(
        'IntegrationInstance.query.filter(' in monitoring, 'runtime monitoring must dispatch from canonical identities'
    )
    for legacy in ('MetricsSource', 'AlertmanagerInstance', 'KubernetesConnection', 'MinioInstance'):
        require(legacy not in monitoring, f'runtime monitoring hard-codes provider model {legacy}')

    require(
        'from app.integrations.storage.object_storage.providers.minio.application.routes import minio_bp' in blueprints,
        'MinIO blueprint import missing',
    )
    require('        minio_bp,' in blueprints, 'MinIO blueprint registration missing')
    require(
        'integration_endpoint_owner(request.endpoint)' in presentation,
        'bootstrap must resolve Integration breadcrumb ownership generically',
    )
    require(
        'integration_owner=integration_owner' in presentation,
        'breadcrumb owner must be passed into common presentation',
    )
    require(
        'integration_owner: Mapping[str, str] | None = None' in breadcrumbs,
        'common breadcrumb must accept resolved Integration ownership',
    )
    require(
        'def integration_endpoint_owner(' in integration_navigation,
        'generic Integration endpoint owner resolver missing',
    )
    require(
        "'domain_label': module.domain.label" in integration_navigation,
        'breadcrumb domain must come from provider taxonomy',
    )

    require('MinIO API Readiness' in minio_detail, 'MinIO detail hero must use the asset-owner API-readiness pattern')
    require(
        'Validation & Capabilities' in minio_detail,
        'MinIO validation workspace must match the Kubernetes capability model',
    )
    require(
        'Inventory & Lifecycle' in minio_detail,
        'MinIO fourth workspace must match the asset-owner inventory/lifecycle model',
    )
    require(
        'provider_configuration_contract.render(' in minio_configuration
        and 'Configure Connection' in provider_configuration_contract,
        'MinIO configuration must expose the shared managed connection lifecycle action',
    )
    require(
        "url_for('minio.edit_instance'" in minio_configuration
        or 'url_for("minio.edit_instance"' in minio_configuration,
        'MinIO configuration edit route is missing',
    )
    require('Lifecycle Gate' in minio_scope, 'MinIO asset lifecycle gate is missing')
    require('Next Lifecycle Action' in minio_scope, 'MinIO lifecycle action summary is missing')
    require('Open Observability' in minio_scope, 'MinIO asset owner must direct binding mutation to Observability')
    require('Delete Connection' in minio_scope, 'MinIO delete action is missing')
    require("url_for('minio.delete_instance'" in minio_scope, 'MinIO delete route wiring is missing')
    require(
        'Validated Capabilities' in minio_validation,
        'MinIO validation workspace must expose the canonical validated-capability presentation',
    )
    require('minio-capability-registry' in minio_capability_registry, 'MinIO capability registry is missing')
    require('capability_per_page' in minio_capability_registry, 'MinIO capability registry pagination is missing')
    require(
        'hx-target="#minio-capability-registry"' in minio_capability_registry,
        'MinIO capability registry must paginate through HTMX',
    )
    require(
        'integrations/partials/_runtime_history.html' in minio_runtime,
        'MinIO runtime history must reuse the canonical runtime-history workspace',
    )
    require('runtime_history_filters_enabled=true' in minio_runtime, 'MinIO runtime history filters must be enabled')
    require('minio-binding-registry' in minio_binding_registry, 'MinIO observability source registry is missing')
    require(
        'Bound Observability Sources' in minio_binding_registry,
        'MinIO must use the asset-owner observability source table',
    )
    require(
        'Binding mutation belongs to the Observability source workspace' in minio_binding_registry,
        'MinIO must keep binding mutation source-owned',
    )
    require('binding_per_page' in minio_binding_registry, 'MinIO consumer binding pagination is missing')
    require(
        'hx-target="#minio-binding-registry"' in minio_binding_registry,
        'MinIO consumer binding registry must paginate through HTMX',
    )
    require(
        "@minio_bp.get('/instances/<int:instance_id>/capabilities/registry')" in minio_routes,
        'MinIO capability HTMX endpoint is missing',
    )
    require(
        "@minio_bp.get('/instances/<int:instance_id>/runtime/history')" in minio_routes,
        'MinIO runtime history HTMX endpoint is missing',
    )
    require(
        "@minio_bp.get('/instances/<int:instance_id>/bindings/registry')" in minio_routes,
        'MinIO binding registry HTMX endpoint is missing',
    )
    for forbidden_route in ('metrics-binding', 'alert-binding', 'validate_binding', 'remove_binding'):
        require(
            forbidden_route not in minio_routes,
            f'MinIO route layer must not own observability binding mutation: {forbidden_route}',
        )
    require('Refresh Runtime' in minio_runtime, 'MinIO manual runtime refresh is missing')
    require("url_for('minio.refresh_runtime'" in minio_runtime, 'MinIO runtime refresh route wiring is missing')
    require(
        "@minio_bp.post('/instances/<int:instance_id>/delete')" in minio_routes,
        'MinIO governed delete endpoint is missing',
    )
    require(
        "@minio_bp.post('/instances/<int:instance_id>/runtime/refresh')" in minio_routes,
        'MinIO runtime refresh endpoint is missing',
    )
    require('def asset_owner_deletion_guard(' in deletion, 'generic asset-owner deletion guard is missing')
    require('def delete_minio_instance(' in service, 'MinIO asset-owner deletion service is missing')
    require(
        'Bound observability source connections remain reusable' in service,
        'MinIO deletion must preserve shared observability sources',
    )

    require(
        '{% call integration_ui.section_header(' not in domain_template,
        'domain section_header caller regression returned',
    )
    require('{{ integration_ui.section_header(' in domain_template, 'domain section_header direct render missing')

    print('PASS — KAORI MinIO Object Storage Provider Foundation')


if __name__ == '__main__':
    main()
