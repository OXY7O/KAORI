from pathlib import Path

from app.reports.storage import health


def test_lightweight_local_readiness_never_scans_artifact_tree(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(health, 'get_local_storage_root_path', lambda: tmp_path)
    monkeypatch.setattr(health, 'get_render_staging_path', lambda: tmp_path)
    monkeypatch.setattr(health, 'get_download_cache_path', lambda: tmp_path)
    monkeypatch.setattr(health, 'is_path_writable', lambda _path: True)

    def forbidden(_path):
        raise AssertionError('recursive artifact walk is forbidden on readiness reads')

    monkeypatch.setattr(health, 'count_files_safe', forbidden)
    monkeypatch.setattr(health, 'sum_files_size_safe', forbidden)

    result = health.build_local_storage_health(include_artifact_inventory=False)
    assert result['root_exists'] is True
    assert result['root_writable'] is True
    assert 'reports_file_count' not in result
    assert 'reports_total_size' not in result
