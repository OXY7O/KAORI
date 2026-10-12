from types import SimpleNamespace

from app.reports.generated import service


def test_empty_report_batch_does_not_lookup_jobs(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError('empty batch must not touch database')
    monkeypatch.setattr(service.db.session, 'scalars', forbidden)
    assert service._get_active_report_generation_ids([]) == set()


def test_canonical_active_job_statuses_match_model() -> None:
    from app.models.job import JobExecution
    assert all(SimpleNamespace(status=status).status in service.ACTIVE_GENERATION_JOB_STATUSES for status in (
        'queued', 'running', 'retrying', 'cancel_requested'
    ))
    # JobExecution.is_active is the authoritative active set used by the shared job engine.
    for status in service.ACTIVE_GENERATION_JOB_STATUSES:
        assert JobExecution.is_active.fget(SimpleNamespace(status=status))
    for status in ('succeeded', 'failed', 'canceled', 'expired'):
        assert not JobExecution.is_active.fget(SimpleNamespace(status=status))


def test_bulk_archive_is_all_or_nothing_for_active_generation(monkeypatch) -> None:
    reports = [
        SimpleNamespace(id=11, status='ready', updated_at=None),
        SimpleNamespace(id=12, status='failed', updated_at=None),
    ]
    calls = {'commit': 0, 'rollback': 0}
    monkeypatch.setattr(service.db.session, 'scalars', lambda *_args: SimpleNamespace(all=lambda: reports))
    monkeypatch.setattr(service, '_get_active_report_generation_ids', lambda _reports: {11})
    monkeypatch.setattr(service.db.session, 'commit', lambda: calls.__setitem__('commit', calls['commit'] + 1))
    monkeypatch.setattr(service.db.session, 'rollback', lambda: calls.__setitem__('rollback', calls['rollback'] + 1))
    success, message = service.bulk_archive_report_records([11, 12])
    assert success is False
    assert 'No reports archived' in message
    assert calls == {'commit': 0, 'rollback': 1}
    assert [report.status for report in reports] == ['ready', 'failed']


def test_single_archive_refuses_active_generation_without_mutation(monkeypatch) -> None:
    report = SimpleNamespace(id=21, status='ready')
    calls = {'commit': 0, 'rollback': 0}
    monkeypatch.setattr(service.db.session, 'scalar', lambda *_args: report)
    monkeypatch.setattr(service, '_get_active_report_generation_ids', lambda _reports: {21})
    monkeypatch.setattr(service.db.session, 'commit', lambda: calls.__setitem__('commit', calls['commit'] + 1))
    monkeypatch.setattr(service.db.session, 'rollback', lambda: calls.__setitem__('rollback', calls['rollback'] + 1))
    success, message = service.archive_report_record(21)
    assert success is False
    assert 'generation is active' in message
    assert report.status == 'ready'
    assert calls == {'commit': 0, 'rollback': 1}
