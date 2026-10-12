from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.artifact_registry.analytics import _valid_instant_vector
from app.artifact_registry.presentation_analytics import _analytics_snapshot_view, _analytics_signal_summary


def test_invalid_metrics_responses_do_not_become_ready_empty_evidence():
    assert not _valid_instant_vector({})
    assert not _valid_instant_vector({'status': 'success', 'data': {'result': []}})
    assert not _valid_instant_vector({'status': 'error', 'data': {'resultType': 'vector', 'result': []}})
    assert not _valid_instant_vector({'status': 'success', 'data': {'resultType': 'vector', 'result': {}}})
    assert _valid_instant_vector({'status': 'success', 'data': {'resultType': 'vector', 'result': []}})


def test_expired_snapshot_remains_readable_but_cannot_claim_current(monkeypatch):
    from app.artifact_registry import presentation_common
    monkeypatch.setattr(presentation_common, '_registry_analytics_inputs_changed', lambda _snapshot: False)
    now = datetime.now(UTC)
    expired = SimpleNamespace(
        status='ready',
        payload_json={'inventory': {'artifacts': 1}},
        generated_at=now - timedelta(hours=3),
        expires_at=now - timedelta(hours=2),
    )
    view = _analytics_snapshot_view(SimpleNamespace(id=42), expired)
    assert view['snapshot'] is expired
    assert view['status_label'] == 'Stale Snapshot'
    assert view['is_current'] is False
    assert _analytics_signal_summary(
        {
            'critical_runtime_artifacts': 0, 'tag_only_bindings': 0,
            'runtime_scan_gaps': 0, 'unsigned_runtime_artifacts': 0,
            'stale_candidates': 0, 'metric_capability_gaps': 0,
        },
        [view],
    )[2]['label'] == 'Snapshot Attention'


def test_missing_expiry_is_not_current(monkeypatch):
    from app.artifact_registry import presentation_common
    monkeypatch.setattr(presentation_common, '_registry_analytics_inputs_changed', lambda _snapshot: False)
    now = datetime.now(UTC)
    legacy = SimpleNamespace(
        status='ready', payload_json={'inventory': {}},
        generated_at=now, expires_at=None,
    )
    assert _analytics_snapshot_view(SimpleNamespace(id=11), legacy)['is_current'] is False


def test_all_instant_metric_query_failures_are_unavailable(monkeypatch):
    from app.artifact_registry import analytics

    class Consumer:
        config = SimpleNamespace(name='Metrics')
        binding = SimpleNamespace(id=1)

        def query(self, _expression):
            return {'status': 'success', 'data': {'resultType': 'vector', 'result': 'invalid'}}

    monkeypatch.setattr(analytics.MetricsConsumer, 'for_asset', lambda **_kw: Consumer())
    observed = analytics._metrics_evidence(SimpleNamespace(id=2, name='registry'))
    assert observed['status'] == 'unavailable'
    assert len(observed['capability_gaps']) == 11


def test_some_instant_metrics_succeed_while_others_fail_is_partial(monkeypatch):
    from app.artifact_registry import analytics

    class Consumer:
        config = SimpleNamespace(name='Metrics')
        binding = SimpleNamespace(id=1)

        def __init__(self):
            self.calls = 0

        def query(self, _expression):
            self.calls += 1
            if self.calls == 1:
                return {'status': 'success', 'data': {'resultType': 'vector', 'result': []}}
            return {'status': 'failure', 'data': None}

    monkeypatch.setattr(analytics.MetricsConsumer, 'for_asset', lambda **_kw: Consumer())
    observed = analytics._metrics_evidence(SimpleNamespace(id=2, name='registry'))
    assert observed['status'] == 'partial'
    assert len(observed['capability_gaps']) == 10


def test_malformed_connected_alertmanager_payload_cannot_be_ready(monkeypatch):
    from app.artifact_registry import analytics

    monkeypatch.setattr(
        analytics, 'list_alerts_for_scope',
        lambda **_kw: {'connected': True, 'alerts': {'not': 'a list'}},
    )
    observed = analytics._alert_evidence(SimpleNamespace(id=2, name='registry'))
    assert observed['status'] == 'unavailable'
    assert observed['rows'] == []
