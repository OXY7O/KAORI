from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_provider_metrics_is_safe_explicit_usage_strategy() -> None:
    config = read('app/config/default.py')
    sync = read('app/storage_inventory/sync.py')
    client = read('app/integrations/minio/client.py')

    assert "{'disabled', 'provider_metrics', 'full_scan'}" in config
    assert 'usage_stats_mode=usage_stats_mode' in sync
    assert "resolved_usage_mode not in {'disabled', 'provider_metrics', 'full_scan'}" in client
    assert "if resolved_usage_mode == 'provider_metrics':" in client
    assert "elif usage_stats_mode == 'full_scan':" in client
    assert "usage_stats_mode or ('full_scan' if collect_usage_stats else 'disabled')" in client


def test_minio_provider_metrics_uses_one_admin_data_usage_snapshot() -> None:
    client = read('app/integrations/minio/client.py')
    assert "f'/minio/admin/{api_version}/datausageinfo'" in client
    assert "params={'capacity': 'true'}" in client
    assert "payload.get('bucketsUsageInfo')" in client
    assert "'objectsCount' not in raw_usage" in client
    assert 'def _coerce_non_negative_usage_counter(value: object) -> int | None:' in client
    assert "_coerce_non_negative_usage_counter(raw_usage.get('size'))" in client
    assert "_coerce_non_negative_usage_counter(raw_usage.get('objectsCount'))" in client
    assert "int(raw_usage.get('size'))" not in client
    assert "int(raw_usage.get('objectsCount'))" not in client
    assert "source = f'minio_admin_data_usage_{api_version}'" in client
    assert "usage_collection = 's3_list_objects_v2'" in client
    assert 'provider_usage = _minio_admin_data_usage(' in client
    assert '_collect_bucket_usage_stats(client, name)' in client


def test_provider_metrics_never_silently_falls_back_to_full_scan() -> None:
    client = read('app/integrations/minio/client.py')
    provider_branch = client.split("if usage_stats_mode == 'provider_metrics':", 1)[1].split(
        "elif usage_stats_mode == 'full_scan':", 1
    )[0]
    assert '_collect_bucket_usage_stats' not in provider_branch
    assert 'list_objects_v2' not in provider_branch


def test_bucket_modal_surfaces_usage_strategy_and_source() -> None:
    presentation = read('app/storage_inventory/presentation.py')
    template = read('app/templates/object_storage_inventory/buckets/partials/_table_content.html')

    assert "return 'Provider Metrics'" in presentation
    assert "return 'MinIO Admin Data Usage v3'" in presentation
    assert "'usage_collection_label': _usage_collection_label(provider_metadata)" in presentation
    assert "detail_ui.detail_row('Usage Source', asset.usage_collection_label)" in template
    assert 'Prefer provider_metrics for scalable usage collection' in template
    assert 'without enumerating every object' in template


def test_environment_examples_keep_provider_metrics_opt_in() -> None:
    for relative in ('.env.example', '.env.production.example'):
        content = read(relative)
        assert 'OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE=disabled' in content
        assert 'provider_metrics' in content
        assert 'admin:DataUsageInfo' in content
        assert 'full_scan' in content
