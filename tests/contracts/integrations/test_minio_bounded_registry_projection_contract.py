"""MinIO Integration registries must page SQL before projecting provider rows."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minio_index_registry_uses_bounded_sql_and_aggregate_counts() -> None:
    presentation = source(
        'app/integrations/storage/object_storage/providers/minio/application/presentation.py'
    )
    index = presentation.split('def build_index_context(', 1)[1].split('def _metrics_source_label(', 1)[0]
    assert 'paginate_query(' in index
    assert '_minio_portfolio_stats(' in index
    assert 'for instance in registry_instances:' in index
    assert 'for instance in coverage_instances:' in index
    assert 'MinioInstance.query.join(MinioInstance.integration_instance).order_by(' not in index
    assert 'for instance in instances:' not in index
    assert 'registry_instances, pagination = paginate_query(' in index
    assert 'coverage_instances, coverage_pagination = paginate_query(' in index
    assert "func.sum(case((metrics_exists, 1), else_=0))" in presentation
    assert 'IntegrationBinding.asset_key == MinioInstance.object_storage_system_id' in presentation


def test_minio_detail_uses_sql_bucket_count_and_bounded_source_page() -> None:
    presentation = source(
        'app/integrations/storage/object_storage/providers/minio/application/presentation.py'
    )
    sources = source('app/integrations/asset_owner_sources.py')
    detail = presentation.split('def build_detail_context(', 1)[1].split(
        'def build_minio_capability_registry(', 1
    )[0]
    assert 'paginate_bound_observability_source_rows(' in detail
    assert "binding_pagination['total_items']" in detail
    assert 'ObjectStorageBucket.query.filter_by(' in detail
    assert '.count()' in detail
    assert 'len(instance.object_storage_system.buckets' not in detail
    page = sources.split('def paginate_bound_observability_source_rows(', 1)[1].split(
        'def _project_bound_source_rows(', 1
    )[0]
    assert 'paginate_query(' in page
    assert '_project_bound_source_rows(bindings)' in page
