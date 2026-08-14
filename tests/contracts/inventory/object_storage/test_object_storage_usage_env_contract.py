from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_object_storage_usage_stats_mode_is_documented_in_environment_examples() -> None:
    for path in ('.env.example', '.env.production.example'):
        content = read(path)
        assert 'OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE=disabled' in content
        assert 'provider_metrics' in content
        assert 'admin:DataUsageInfo' in content
        assert 'full_scan' in content
        assert 'used size or object count' in content
