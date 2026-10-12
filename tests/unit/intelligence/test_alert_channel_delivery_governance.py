from __future__ import annotations

from types import SimpleNamespace

from app.intelligence.alert_intelligence import notifications, routing


def test_resolved_channels_are_pending_independently() -> None:
    channels = {1: True, 2: True, 3: False}
    assert notifications._pending_resolved_channel_ids(channels, {1}) == [2]
    assert notifications._pending_resolved_channel_ids(channels, {1, 2}) == []


def test_partial_resolved_delivery_retries_only_failed_channel(monkeypatch) -> None:
    delivered = {1}
    calls = []
    commits = []
    case = SimpleNamespace(
        domain='kubernetes', public_id='CASE-42',
        last_resolved_notified_at=None,
    )
    monkeypatch.setattr(notifications, '_successful_firing_channels', lambda _case: {1: True, 2: True})
    monkeypatch.setattr(notifications, '_successful_resolved_channels', lambda _case: set(delivered))
    monkeypatch.setattr(notifications, '_timeline', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        notifications, 'db',
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(True))),
    )

    def send(_case, *, channel_id, event_state, sequence):
        calls.append((channel_id, event_state, sequence))
        # Simulate retry still failing during first pass.
        if len(calls) == 1:
            return {'successful': 0, 'failed': 1, 'skipped': 0}
        delivered.add(channel_id)
        return {'successful': 1, 'failed': 0, 'skipped': 0}

    monkeypatch.setattr(notifications, '_deliver_case_event', send)
    first = notifications._dispatch_resolved(case)
    assert first['failed'] == 1
    assert case.last_resolved_notified_at is None
    assert commits == []
    second = notifications._dispatch_resolved(case)
    assert second['resolved'] == 1
    assert case.last_resolved_notified_at is not None
    assert calls == [(2, 'resolved', 'final'), (2, 'resolved', 'final')]
    assert commits == [True]


def test_enabled_policy_mismatch_must_not_fall_back_to_default_channels(monkeypatch) -> None:
    class PolicyQuery:
        def filter(self, *_args):
            return self
        def all(self):
            return [SimpleNamespace(domains_json=['kubernetes'])]

    monkeypatch.setattr(routing, 'matching_routing_policies', lambda _case: [])
    monkeypatch.setattr(
        routing, 'AlertRoutingPolicy',
        SimpleNamespace(query=PolicyQuery(), domains_json=SimpleNamespace(is_not=lambda _: True)),
    )
    case = SimpleNamespace(
        domain='kubernetes', source_type='recommendation',
        source_state='firing', routing_state='enabled',
        severity='critical',
    )
    assert routing.firing_routes(case) == []
    assert routing.policy_allows_resolved(case, 42) is False


def test_closed_case_dispatch_requires_successful_firing_evidence() -> None:
    """Source guard: pending resolved work cannot be inferred from case closure alone."""
    import inspect

    text = inspect.getsource(notifications.dispatch_case_notifications)
    assert 'had_successful_firing' in text
    assert "NotificationDelivery.event_type == 'alert_ops.firing'" in text
    assert "NotificationDelivery.status == 'sent'" in text
    assert "AlertCase.domain != 'registry'" in text
