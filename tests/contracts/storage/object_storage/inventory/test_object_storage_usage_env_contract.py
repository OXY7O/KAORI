from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_object_storage_usage_stats_mode_is_documented_in_environment_examples() -> None:
    development = read('.env.example')
    production = read('deploy/env/app.env.example')

    assert 'OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE=disabled' in development
    assert 'OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE=disabled' in production
    for marker in ('provider_metrics', 'admin:DataUsageInfo', 'full_scan', 'used size or object count'):
        assert marker in development
