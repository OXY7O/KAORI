from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.artifact_registry import correlation


def _readiness(*, committed_signature: str | None, current_signature: str = 'current'):
    now = datetime.now(UTC)
    success = SimpleNamespace(
        result_summary_json={'input_signature': committed_signature},
        completed_at=now,
        created_at=now - timedelta(minutes=1),
        is_active=False,
        status='succeeded',
    )
    session = MagicMock()
    jobs = session.query.return_value.filter.return_value
    jobs.order_by.return_value.first.return_value = success
    jobs.filter.return_value.order_by.return_value.first.return_value = success
    return session


def test_correlation_readiness_detects_changed_committed_generations(monkeypatch):
    monkeypatch.setattr(correlation, 'runtime_input_signature', lambda session: 'current')
    session = _readiness(committed_signature='previous')
    state = correlation.runtime_correlation_evidence_readiness(session)
    assert state['status'] == 'inputs_changed'
    assert 'not remediated' in state['description']
    assert 'Refresh Runtime Correlation' in state['description']


def test_correlation_readiness_accepts_matching_generation_signature(monkeypatch):
    monkeypatch.setattr(correlation, 'runtime_input_signature', lambda session: 'current')
    session = _readiness(committed_signature='current')
    assert correlation.runtime_correlation_evidence_readiness(session)['status'] == 'ready'


def test_correlation_readiness_requires_materialized_evidence(monkeypatch):
    monkeypatch.setattr(correlation, 'runtime_input_signature', lambda session: 'current')
    session = MagicMock()
    jobs = session.query.return_value.filter.return_value
    jobs.order_by.return_value.first.return_value = None
    jobs.filter.return_value.order_by.return_value.first.return_value = None
    assert correlation.runtime_correlation_evidence_readiness(session)['status'] == 'not_materialized'
