from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_minio_usage_state_distinguishes_disabled_from_collection_failure():
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')
    assert "usage_state = 'disabled'" in client
    assert "if usage_stats_mode == 'provider_metrics':" in client
    assert "elif usage_stats_mode == 'full_scan':" in client
    assert "usage_state = 'not_collected'" in client
    assert "usage_state = 'collected'" in client


def test_bucket_detail_keeps_usage_evidence_out_of_the_inventory_table() -> None:
    table = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')
    table_head = table.split('<thead', 1)[1].split('</thead>', 1)[0]

    assert '>Quota<' in table_head
    assert '>Size<' not in table_head
    assert '>Objects<' not in table_head
    assert 'Used Size' in detail
    assert 'Current Objects' in detail
    assert 'full_scan' in detail


def test_provider_api_endpoint_uses_full_width_resource_sheet_row() -> None:
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert "detail.inventory_technical_row('API Endpoint', bucket.endpoint" in detail
    assert "class_name='lg:col-span-2'" in detail
    assert "stacked_detail_row('API Endpoint'" not in detail


def test_detail_replaces_sparse_native_evidence_with_curated_provider_context() -> None:
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    assert 'Provider Context' in detail
    assert 'Enrichment Profile' in detail
    assert 'Usage Strategy' in detail
    assert 'Quota Source' in detail
    assert 'Native Provider Evidence' not in presentation
