"""Recommendation delivery mode is independent of collection and provider authority."""

from types import SimpleNamespace

import pytest

from app.integrations.delivery.notification_channels import service as delivery
from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.intelligence.alert_intelligence import delivery_mode, notifications, routing


def case_stub(**changes):
    values = dict(
        public_id='CASE-1', domain='kubernetes', asset_type='cluster', asset_key='cluster-1',
        source_type='recommendation', source_state='firing', routing_state='enabled',
        workflow_state='open', severity='critical',
    )
    return SimpleNamespace(**(values | changes))


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def filter_by(self, **_kwargs):
        return self

    def order_by(self, *_args):
        return self

    def populate_existing(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


@pytest.mark.parametrize(
    ('mode', 'expected'),
    [('channel_defaults', 1), ('policy_required', 0), ('delivery_disabled', 0)],
)
def test_no_policy_firing_matrix(monkeypatch, mode, expected):
    monkeypatch.setattr(routing, 'effective_routing_mode', lambda: mode)
    monkeypatch.setattr(routing, 'matching_routing_policies', lambda _case: [])
    monkeypatch.setattr(
        routing, 'AlertRoutingPolicy',
        SimpleNamespace(query=Query([]), domains_json=SimpleNamespace(is_not=lambda _: True)),
    )
    channel = SimpleNamespace(
        id=7, configured=True, test_status='success', domains=['kubernetes'],
        event_types=['alert_ops.firing'],
    )
    monkeypatch.setattr(
        routing, 'NotificationChannel',
        SimpleNamespace(query=Query([channel]), id=SimpleNamespace(asc=lambda: None)),
    )
    routes = routing.firing_routes(case_stub())
    assert len(routes) == expected
    if routes:
        assert routes[0].route_key == 'default'
        assert routes[0].repeat_interval_minutes == 5


@pytest.mark.parametrize(
    ('mode', 'expected'),
    [('channel_defaults', True), ('policy_required', True), ('delivery_disabled', False)],
)
def test_matching_policy_firing_and_resolved_matrix(monkeypatch, mode, expected):
    policy = SimpleNamespace(id=5, channel_ids_json=[7], repeat_interval_minutes=15, send_resolved=True)
    monkeypatch.setattr(routing, 'effective_routing_mode', lambda: mode)
    monkeypatch.setattr(routing, 'matching_routing_policies', lambda _case: [policy])
    routes = routing.firing_routes(case_stub())
    assert bool(routes) is expected
    assert routing.policy_allows_resolved(case_stub(), 7) is expected
    assert not routing.policy_allows_resolved(case_stub(), 8)
    if routes:
        assert routes[0].route_key == 'policy-5'


def event_args(**changes):
    values = dict(
        domain='kubernetes', event_type='alert_ops.firing', asset_type='cluster', asset_key='cluster-1',
        event_key='alert-case:CASE-1:firing:route-policy-5:10', channel_id=7,
        payload={'case_id': 'CASE-1', 'routing_policy_id': 5},
    )
    return values | changes


def test_strict_transport_requires_exact_current_case_route(monkeypatch):
    monkeypatch.setattr(delivery_mode, 'effective_routing_mode', lambda: 'policy_required')
    case = case_stub()
    monkeypatch.setattr(delivery_mode, 'AlertCase', SimpleNamespace(query=Query([case])))
    monkeypatch.setattr(routing, 'firing_routes', lambda _case: [routing.FiringRoute(5, 7, 15, True)])
    assert delivery_mode.recommendation_event_allowed(**event_args())
    for changes in (
        {'channel_id': 8}, {'asset_key': 'foreign'}, {'asset_type': 'foreign'},
        {'event_key': 'alert-case:CASE-1:firing:route-default:10'},
        {'payload': {'case_id': 'CASE-1', 'routing_policy_id': None}},
        {'payload': {'case_id': 'CASE-1', 'routing_policy_id': True}},
        {'event_type': 'alert_intelligence.active_alert'},
    ):
        assert not delivery_mode.recommendation_event_allowed(**event_args(**changes))
    case.workflow_state = 'closed'
    assert not delivery_mode.recommendation_event_allowed(**event_args())


def test_strict_resolved_requires_matching_policy_and_prior_firing(monkeypatch):
    monkeypatch.setattr(delivery_mode, 'effective_routing_mode', lambda: 'policy_required')
    case = case_stub(source_state='resolved', workflow_state='closed')
    monkeypatch.setattr(delivery_mode, 'AlertCase', SimpleNamespace(query=Query([case])))
    monkeypatch.setattr(routing, 'policy_allows_resolved', lambda _case, channel: channel == 7)
    actual_model = delivery_mode.NotificationDelivery
    rows = Query([])
    monkeypatch.setattr(
        delivery_mode, 'NotificationDelivery',
        SimpleNamespace(
            query=rows, channel_id=actual_model.channel_id, event_type=actual_model.event_type,
            status=actual_model.status, event_key=actual_model.event_key,
        ),
    )
    args = event_args(
        event_type='alert_ops.resolved', event_key='alert-case:CASE-1:resolved:final',
        payload={'case_id': 'CASE-1'},
    )
    assert not delivery_mode.recommendation_event_allowed(**args)
    rows.rows = [SimpleNamespace(id=1)]
    assert delivery_mode.recommendation_event_allowed(**args)
    assert not delivery_mode.recommendation_event_allowed(**(args | {'channel_id': 8}))
    case.workflow_state = 'verification_pending'
    assert not delivery_mode.recommendation_event_allowed(**args)


def test_default_legacy_never_bypasses_governed_domain_or_registry(monkeypatch):
    monkeypatch.setattr(delivery_mode, 'effective_routing_mode', lambda: 'channel_defaults')
    monkeypatch.setattr(delivery_mode, '_domain_governed', lambda domain: domain == 'kubernetes')
    assert not delivery_mode.recommendation_event_allowed(
        **event_args(event_type='alert_intelligence.active_alert')
    )
    assert delivery_mode.recommendation_event_allowed(
        **event_args(domain='object_storage', event_type='alert_intelligence.active_alert')
    )
    assert not delivery_mode.recommendation_event_allowed(
        **event_args(domain='registry', event_type='alert_intelligence.active_alert')
    )
    assert not delivery_mode.recommendation_event_allowed(
        **event_args(payload={'routing_policy_id': None})
    )


def test_disabled_blocks_transport_and_resolved_but_not_unrelated_event(monkeypatch):
    monkeypatch.setattr(delivery_mode, 'effective_routing_mode', lambda: 'delivery_disabled')
    for event_type in delivery_mode.EVENTS:
        assert not delivery_mode.recommendation_event_allowed(**event_args(event_type=event_type))
    assert delivery_mode.recommendation_event_allowed(**event_args(event_type='report.generated'))
    assert delivery_mode.recommendation_event_allowed(**event_args(domain='secrets_pki'))
    event = NotificationEvent(
        domain='kubernetes', event_type='alert_ops.firing', asset_type='cluster', asset_key='cluster-1',
        severity='critical', event_key='alert-case:CASE-1:firing:route-policy-5:10',
        message=NotificationMessage(title='Alert', body='Test only', severity='critical'), payload={},
    )
    stats = delivery.dispatch_notification_event(channel_ids=[7], event=event)
    assert stats['skipped'] == 1 and stats['successful'] == 0
    monkeypatch.setattr(notifications, 'effective_routing_mode', lambda: 'delivery_disabled')
    result = notifications._dispatch_resolved(case_stub(source_state='resolved', workflow_state='closed'))
    assert result == {'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 1}


def test_missing_or_invalid_mode_fails_closed(monkeypatch):
    for row in (None, SimpleNamespace(mode='unknown', revision=1)):
        monkeypatch.setattr(
            delivery_mode, 'db',
            SimpleNamespace(session=SimpleNamespace(
                execute=lambda _statement: SimpleNamespace(one_or_none=lambda: row),
            )),
        )
        assert delivery_mode.routing_mode_view() == {
            'mode': 'delivery_disabled', 'revision': None, 'available': False,
        }


def test_mode_change_audits_revision_and_rejects_stale_form(monkeypatch):
    row = SimpleNamespace(mode='channel_defaults', revision=1)
    events = []
    commits = []
    rollbacks = []
    session = SimpleNamespace(
        get=lambda *args, **kwargs: row, add=events.append,
        commit=lambda: commits.append(True), rollback=lambda: rollbacks.append(True),
    )
    monkeypatch.setattr(delivery_mode, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(delivery_mode, 'AuditEvent', SimpleNamespace)
    assert delivery_mode.save_routing_mode(mode='policy_required', revision=1, actor_user_id=4)
    assert row.mode == 'policy_required' and row.revision == 2
    assert commits == [True]
    assert events[0].actor_user_id == 4
    assert events[0].metadata_json == {
        'previous_mode': 'channel_defaults', 'mode': 'policy_required', 'revision': 2,
    }
    with pytest.raises(ValueError):
        delivery_mode.save_routing_mode(mode='delivery_disabled', revision=1, actor_user_id=4)
    with pytest.raises(ValueError):
        delivery_mode.save_routing_mode(mode='invalid', revision=2, actor_user_id=4)
    assert not delivery_mode.save_routing_mode(mode='policy_required', revision=2, actor_user_id=4)
    assert row.mode == 'policy_required' and row.revision == 2
    assert len(events) == len(commits) == 1
    assert rollbacks == [True]
