from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict

from app.intelligence.alert_intelligence import routing, service
from app.intelligence.alert_intelligence.notifications import _dispatch_resolved


class _Column:
    def __eq__(self, _value: object) -> bool:
        return True

    def is_(self, _value: object) -> bool:
        return True

    def asc(self) -> "_Column":
        return self


class _ProvidersQuery:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def filter(self, *_criteria: object) -> "_ProvidersQuery":
        return self

    def order_by(self, *_columns: object) -> "_ProvidersQuery":
        return self

    def all(self) -> list[SimpleNamespace]:
        return self.rows


def test_registry_provider_choices_exclude_inactive_disabled_and_blocked(monkeypatch) -> None:
    rows = [
        SimpleNamespace(id=7, name='Harbor A', environment='UAT', enabled=True, lifecycle_status='active', readiness_status='ready'),
        SimpleNamespace(id=8, name='Harbor B', environment='UAT', enabled=False, lifecycle_status='active', readiness_status='ready'),
        SimpleNamespace(id=9, name='Harbor C', environment='UAT', enabled=True, lifecycle_status='retired', readiness_status='ready'),
        SimpleNamespace(id=10, name='Harbor D', environment='UAT', enabled=True, lifecycle_status='active', readiness_status='blocked'),
    ]
    column = _Column()
    fake_model = SimpleNamespace(
        query=_ProvidersQuery(rows),
        integration_type=column,
        enabled=column,
        lifecycle_status=column,
        name=column,
        id=column,
    )
    monkeypatch.setattr(service, 'IntegrationInstance', fake_model)

    assert service._selected_domain(MultiDict([('domain', 'registry')]), clusters=[], systems=[]) == 'registry'
    options = service._asset_options('registry', clusters=[], systems=[])
    assert [option['value'] for option in options] == ['all', '7']
    assert options[1]['label'] == 'Harbor A'
    assert options[1]['environment'] == 'UAT'

    assert service._selected_asset_key(MultiDict([('asset', '7')]), options, domain='registry') == '7'
    assert (
        service._selected_asset_key(MultiDict([('asset', '8')]), options, domain='registry')
        == service._INVALID_REGISTRY_SCOPE
    )
    assert (
        service._selected_asset_key(MultiDict([('asset', 'unknown')]), options, domain='registry')
        == service._INVALID_REGISTRY_SCOPE
    )
    assert service._selected_asset_key(MultiDict(), options, domain='registry') == 'all'
    assert service._selected_asset_key(MultiDict([('asset', 'stale')]), options, domain='kubernetes') == 'all'


def test_case_selection_is_constrained_to_active_domain_and_asset_scope() -> None:
    own = SimpleNamespace(public_id='CASE-REG-7')
    other_domain_or_provider = 'CASE-K8S-8'
    assert service._selected_case('CASE-REG-7', [own]) is own
    assert service._selected_case(other_domain_or_provider, [own]) is None
    assert service._selected_case(None, [own]) is None


def test_registry_routing_and_resolved_delivery_remain_fail_closed() -> None:
    case = SimpleNamespace(
        domain='registry',
        source_type='recommendation',
        source_state='firing',
        routing_state='enabled',
        severity='critical',
    )
    assert routing.matching_routing_policies(case) == []
    assert routing.firing_routes(case) == []
    assert routing.policy_allows_resolved(case, 1) is False

    case.source_state = 'resolved'
    assert _dispatch_resolved(case) == {'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 1}


def test_registry_routing_policy_cannot_be_enabled_implicitly() -> None:
    policy = routing.RoutingPolicyConfig(
        name='Unapproved Registry Route',
        enabled=True,
        domains=['registry', 'kubernetes'],
        severities=['critical'],
        source_types=['recommendation'],
        channel_ids=[1],
        repeat_interval_minutes=15,
        acknowledgement_timeout_minutes=30,
        send_resolved=True,
        matchers={},
    )
    with pytest.raises(ValueError, match='Registry notification routing is not enabled'):
        routing.upsert_routing_policy(policy_id=None, config=policy, actor_user_id=1)
