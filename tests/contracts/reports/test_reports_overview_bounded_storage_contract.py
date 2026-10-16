from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_overview_only_constructs_selected_backend_lightweight_health() -> None:
    service = read('app/reports/overview/service.py')
    assert "if backend_name == 'local'" in service
    assert "if backend_name == 's3' else None" in service
    assert 'build_local_storage_health(include_artifact_inventory=False)' in service


def test_backend_readiness_skips_recursive_census_without_removing_storage_diagnostics() -> None:
    health = read('app/reports/storage/health.py')
    service = read('app/reports/storage/service.py')
    assert 'include_artifact_inventory: bool = True' in health
    assert 'if include_artifact_inventory:' in health
    assert 'build_local_storage_health(include_artifact_inventory=False)' in service
    assert 'build_local_storage_health()' not in service
