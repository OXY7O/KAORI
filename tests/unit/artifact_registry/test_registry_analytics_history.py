from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.artifact_registry.analytics import _growth_payload
from app.artifact_registry import analytics_history


def test_historical_window_is_real_measured_range_with_bounded_step():
    now = datetime(2026, 10, 12, tzinfo=UTC)
    start, end, step = analytics_history.history_plan('60d', now=now)
    assert end - start == timedelta(days=60)
    assert step >= 60
    assert (end - start).total_seconds() / step <= analytics_history.MAX_HISTORY_POINTS


def _matrix(start: datetime, end: datetime, *, project='library', first=0, last=5):
    return {
        'status': 'success',
        'data': {'resultType': 'matrix', 'result': [
            {'metric': {'project_name': project}, 'values': [
                [start.timestamp(), str(first)], [end.timestamp(), str(last)]
            ]}
        ]},
    }


def test_bounded_matrix_accepts_true_zero_baseline_with_full_interval():
    start, end, step = analytics_history.history_plan(
        '1h', now=datetime(2026, 10, 12, tzinfo=UTC)
    )
    data = analytics_history._bounded_matrix(
        _matrix(start, end), project_scoped=True,
        start_at=start, end_at=end, step_seconds=step,
    )
    assert data['library']['first'] == 0
    assert data['library']['last'] == 5


def test_historical_coverage_shorter_than_selected_range_fails_closed():
    start, end, step = analytics_history.history_plan(
        '60d', now=datetime(2026, 10, 12, tzinfo=UTC)
    )
    recent = end - timedelta(days=1)
    with pytest.raises(ValueError, match='retention'):
        analytics_history._bounded_matrix(
            _matrix(recent, end), project_scoped=True,
            start_at=start, end_at=end, step_seconds=step,
        )


def test_malformed_success_and_excessive_cardinality_are_not_ready():
    start, end, step = analytics_history.history_plan(
        '1h', now=datetime(2026, 10, 12, tzinfo=UTC)
    )
    with pytest.raises(ValueError):
        analytics_history._bounded_matrix(
            {'status': 'success', 'data': {'resultType': 'vector', 'result': []}},
            project_scoped=True, start_at=start, end_at=end, step_seconds=step,
        )
    rows = [_matrix(start, end, project=str(i))['data']['result'][0] for i in range(251)]
    with pytest.raises(ValueError, match='budget'):
        analytics_history._bounded_matrix(
            {'status': 'success', 'data': {'resultType': 'matrix', 'result': rows}},
            project_scoped=True, start_at=start, end_at=end, step_seconds=step,
        )


def test_worker_queries_real_range_and_preserves_zero_growth_baseline(monkeypatch):
    now = datetime(2026, 10, 12, tzinfo=UTC)
    calls = []
    class Consumer:
        config = SimpleNamespace(name='Prometheus')
        binding = SimpleNamespace(id=12)
        def query_range(self, expression, start, end, step, *, retry_count):
            calls.append((expression, start, end, step, retry_count))
            return _matrix(datetime.fromisoformat(start), datetime.fromisoformat(end))
    monkeypatch.setattr(
        analytics_history.MetricsConsumer, 'for_asset', lambda **_kwargs: Consumer()
    )
    history, metrics, growth = analytics_history.collect_registry_metric_history(
        SimpleNamespace(id=7, name='registry-7'), '1h', now=now,
    )
    assert len(calls) == len(analytics_history.HISTORY_QUERIES)
    assert history['status'] == 'ready'
    assert metrics['status'] == 'ready'
    assert growth['artifact_delta'] == 5
    assert history['time_range'] == '1h'


def test_previous_snapshot_zero_is_not_treated_as_absent():
    now = datetime(2026, 10, 12, tzinfo=UTC)
    previous = SimpleNamespace(
        generated_at=now - timedelta(days=1),
        payload_json={'inventory': {'artifacts': 0, 'total_size_bytes': 0}},
    )
    growth, elapsed = _growth_payload(previous, generated_at=now, artifact_count=8, total_size=4096)
    assert elapsed == 1
    assert growth['artifact_delta'] == 8
    assert growth['size_delta_bytes'] == 4096
