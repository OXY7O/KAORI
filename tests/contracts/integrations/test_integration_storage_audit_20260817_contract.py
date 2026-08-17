from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_storage_domain_keeps_owner_and_observability_source_boundaries_explicit() -> None:
    taxonomy = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    registration = read('app/integrations/minio/__init__.py')

    assert '- key: storage' in taxonomy
    assert '- key: object_storage' in taxonomy
    assert '- key: file_storage' in taxonomy
    assert '- key: block_storage' in taxonomy
    assert "domain_key='storage'" in registration
    assert "capability_key='object_storage'" in registration
    assert 'data-kaori-storage-binding-boundary' in workspace
    assert 'MinIO owns the object-storage API and managed asset.' in workspace
    assert 'A Metrics Source provides metrics' in workspace
    assert 'File Storage and Block Storage remain capability placeholders' in workspace


def test_storage_asset_owner_projection_uses_metrics_provider_registry() -> None:
    projection = read('app/integrations/asset_owner_sources.py')
    coverage = read('app/minio/presentation.py')
    coverage_template = read('app/templates/minio/partials/_coverage_content.html')

    assert 'def _source_presentation(' in projection
    assert "canonical.integration_type != 'metrics_source'" in projection
    assert 'canonical.provider_key' in projection
    assert 'definition = provider_definition(provider_key)' in projection
    assert 'return definition.label, definition.icon' in projection
    assert 'def _metrics_source_label(source: object | None) -> str:' in coverage
    assert 'provider_definition(provider_key).label' in coverage
    assert 'row.metrics_source_label' in coverage_template
    assert 'No Prometheus binding' not in coverage_template


def test_minio_registration_test_does_not_claim_product_identity_authority() -> None:
    form = read('app/templates/minio/instance_form.html')
    routes = read('app/minio/routes.py')
    service = read('app/minio/service.py')

    assert 'Verify S3 API reachability, credential access, and read-only bucket discovery' in form
    assert 'Verify MinIO identity and API reachability' not in form
    assert "title='S3 API connection verified'" in routes
    assert 'submitted S3-compatible API endpoint with the provided credential' in routes
    assert 'Product identity and release compatibility remain authoritative Core Validation evidence.' in service


def test_minio_bound_source_registry_hides_empty_pagination_and_uses_metrics_source_copy() -> None:
    registry = read('app/templates/minio/partials/_binding_registry.html')
    scope = read('app/templates/minio/partials/_detail_scope.html')
    index = read('app/templates/minio/index.html')

    assert '{% if binding_pagination.total_items > 0 %}' in registry
    assert 'Metrics Source or Alertmanager' in registry
    assert 'Metrics Source and Alertmanager remain reusable source-owned connections' in scope
    assert 'Metrics Source owns metrics by source identity' in index
