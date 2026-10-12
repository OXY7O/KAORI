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
