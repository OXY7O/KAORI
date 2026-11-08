from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_dispatcher_commits_asset_aware_integration_ownership() -> None:
    source = (ROOT / 'app/reports/jobs/service.py').read_text()
    assert "'registry_integration': 'registry'" in source
    assert "'object_storage_system': 'object_storage'" in source
    assert "'kubernetes_cluster': 'kubernetes'" in source
    assert 'integration_type=integration_type' in source
    assert 'integration_instance_id=integration_instance_id' in source
    assert 'scope_type=parameters.scope_asset_type' in source
    assert 'scope_key=parameters.scope_asset_id' in source
    assert 'queue_name=get_reports_queue_name()' in source
    assert "resource_group = f'report:{report.id}'" in source
