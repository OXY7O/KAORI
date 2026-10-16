from types import SimpleNamespace

from app.reports.generated import service


def test_reachable_backend_does_not_imply_report_file_exists(monkeypatch) -> None:
    monkeypatch.setattr(service, '_get_active_storage_backend_name', lambda: 's3')
    monkeypatch.setattr(service, 'get_report_storage_backend_status', lambda _backend: {'reachable': True})
    monkeypatch.setattr(
        service, '_probe_report_file', lambda *_args: (_ for _ in ()).throw(AssertionError('unexpected HEAD'))
    )
    state = service._summarize_report_file_reference('s3:reports/example.pdf')
    assert state['exists'] is False
    assert state['verified'] is False
    assert state['state'] == 'referenced'
    assert (
        service._get_file_state(SimpleNamespace(status='ready', file_path='s3:reports/example.pdf'), state)['label']
        == 'Artifact Referenced'
    )


def test_archived_reference_is_not_presented_as_physically_verified() -> None:
    report = SimpleNamespace(status='archived', file_path='s3:reports/archive.pdf')
    access = {'exists': False, 'verified': False, 'reachable': True, 'state': 'referenced'}
    assert service._get_file_state(report, access)['label'] == 'Archived Reference'


def test_verified_missing_file_remains_a_critical_finding() -> None:
    report = SimpleNamespace(status='ready', file_path='s3:reports/missing.pdf')
    access = {'exists': False, 'reachable': True, 'state': 'missing'}
    assert service._get_file_state(report, access)['label'] == 'Missing File'


def test_unreachable_storage_does_not_impersonate_a_verified_artifact() -> None:
    report = SimpleNamespace(status='ready', file_path='s3:reports/missing.pdf')
    access = {'exists': False, 'verified': False, 'reachable': False, 'state': 'unavailable'}
    assert service._get_file_state(report, access)['label'] == 'Storage Unavailable'
