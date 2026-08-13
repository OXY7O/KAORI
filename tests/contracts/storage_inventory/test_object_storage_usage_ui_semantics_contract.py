from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_minio_usage_state_distinguishes_disabled_from_collection_failure():
    client = read('app/integrations/minio/client.py')
    assert "usage_state = 'disabled'" in client
    assert "if usage_stats_mode == 'provider_metrics':" in client
    assert "elif usage_stats_mode == 'full_scan':" in client
    assert "usage_state = 'not_collected'" in client
    assert "usage_state = 'collected'" in client


def test_bucket_modal_keeps_usage_detail_out_of_the_inventory_table():
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    table_head = template.split('<thead', 1)[1].split('</thead>', 1)[0]
    assert '>Quota<' in table_head
    assert '>Size<' not in table_head
    assert '>Objects<' not in table_head
    assert 'Used Size' in template
    assert 'Current Objects' in template
    assert 'full_scan' in template


def test_provider_api_endpoint_keeps_horizontal_key_value_alignment():
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    assert "detail_row('API Endpoint', asset.endpoint, break_all=true)" in template
    assert "stacked_detail_row('API Endpoint'" not in template


def test_modal_replaces_sparse_native_evidence_with_curated_provider_context():
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')
    presentation = read('app/storage_inventory/presentation.py')
    assert 'Provider Context' in template
    assert 'Enrichment Profile' in template
    assert 'Usage Stats Mode' in template
    assert 'Quota Source' in template
    assert 'Native Provider Evidence' not in presentation
