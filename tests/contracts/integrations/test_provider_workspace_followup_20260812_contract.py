from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_validation_uses_validated_capabilities_copy() -> None:
    workspace = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html'
    )

    assert "'Validated Capabilities'," in workspace
    assert 'Validated capability coverage' not in workspace


def test_minio_validation_has_provider_readiness_explanation() -> None:
    validation = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
    )

    assert '_readiness_explanation.html' in validation
    assert 'Provider Readiness Is Ready' in validation
    assert 'Why Readiness Is Blocked' in validation
    assert 'Why Readiness Needs Attention' in validation
    assert 'readiness_explanation.render(' in validation
    assert validation.index('readiness_explanation.render(') < validation.index('_capability_registry.html')


def test_minio_capability_registry_matches_modal_detail_standard() -> None:
    registry = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html'
    )
    presentation = read('app/integrations/storage/object_storage/providers/minio/application/presentation.py')

    assert '_record_detail_modal.html' in registry
    assert '_provider_capability_detail.html' in registry
    assert '_record_actions.html' in registry
    assert '>Details</th>' in registry
    assert 'record_actions.view_more("minio-capability-detail-" ~ loop.index' in registry
    assert 'record_detail_modal.render(' in registry
    assert '"MinIO Capability Evidence"' in registry
    assert 'provider_capability_detail.content(row,' in registry
    assert "'status_label': 'Ready' if available else 'Blocked'" in presentation
    assert "'source_owner': 'MinIO S3 API'" in presentation
    assert "'technical_checks': []" in presentation


def test_minio_runtime_refresh_isolated_from_history_loader() -> None:
    runtime = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html')
    routes = read('app/integrations/storage/object_storage/providers/minio/application/routes.py')

    refresh_surface = runtime.split('{% if runtime_history_oob|default(false) %}', 1)[0]
    assert 'data-kaori-minio-runtime-refresh-surface' in refresh_surface
    assert 'loading_id="minio-runtime-loading"' in refresh_surface
    assert 'hx-indicator="#minio-runtime-loading"' in refresh_surface
    assert 'minio-history-loading' not in refresh_surface
    assert 'data-kaori-minio-runtime-history-external' in runtime
    assert 'runtime_history_oob=true' in runtime
    assert routes.count('runtime_history_oob=True') >= 2


def test_minio_authority_boundary_has_right_side_metadata_labels() -> None:
    configuration = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html'
    )
    operational_context = read('app/templates/integrations/components/_provider_operational_context.html')

    assert 'data-kaori-authority-boundary-metadata' in operational_context
    assert '"S3 API Authority"' in configuration
    assert '"Read-Only Discovery"' in configuration
    assert '"Region · "' in configuration
    assert '" Addressing"' in configuration
    assert 'operational_metadata=operational_metadata' in configuration


def test_kubernetes_inventory_lifecycle_exposes_binding_ownership() -> None:
    lifecycle = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_inventory_lifecycle.html'
    )

    assert 'data-kaori-kubernetes-binding-ownership' in lifecycle
    assert 'Binding Ownership' in lifecycle
    assert 'Open Observability' in lifecycle
    assert "url_for('integrations.observability')" in lifecycle
    assert 'asset-owner workspace remains read-only for binding mutation' in lifecycle


def test_kubernetes_legacy_primary_finding_is_compact() -> None:
    validation = read('app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/validation.py')

    assert 'is in a legacy lifecycle band.' in validation
    assert 'Plan an upgrade.' in validation
    assert (
        'Stable APIs remain usable, but upgrade planning is required before readiness can return to Ready.'
        not in validation
    )


def test_integrations_title_case_audit_is_enforced() -> None:
    registration = read('app/templates/integrations/components/_provider_registration_hero.html')
    binding_workspace = read('app/templates/integrations/bindings/partials/_workspace.html')
    quality_gate = read('scripts/quality_gate.sh')
    verifier = read('scripts/verify_integrations_title_case.py')

    assert 'Pre-Save Requirements' in registration
    assert 'Pre-save Requirements' not in registration
    assert 'Existing {{ provider.label }} Source' in binding_workspace
    assert 'Source Label' in binding_workspace
    assert 'Label Value for This Scope' in binding_workspace
    assert 'verify_integrations_title_case.py' in quality_gate
    assert "CHECKED_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th', 'label', 'button'}" in verifier
