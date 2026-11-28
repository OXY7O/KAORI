"""AL-05B reserved native recommendation and case admission boundary."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from flask import Flask

from app.intelligence import authentication_recommendations as auth
from app.intelligence import recommendation_alerting as policies
from app.intelligence.alert_intelligence import application, notifications, recommendation_source, routing
from app.intelligence.alert_signals.authentication import closed_window, summarize_abuse

NOW = datetime(2026, 11, 28, 12, 20, tzinfo=UTC)


def _snapshot(*, positive: bool = True) -> dict[str, Any]:
    rows = [
        ({
            'audit_schema': 'authentication.v2',
            'access_action': 'login',
            'result': 'failed',
            'reason_code': 'invalid_credentials',
            'auth_source': 'database',
            'ip_address': '192.0.2.1',
        }, 42, True)
    ] * (5 if positive else 0)
    payload = summarize_abuse(rows)
    start, end = closed_window(NOW)
    payload.update({
        'source_authority': 'committed_activity_audit',
        'window_start': start.isoformat(),
        'window_end': end.isoformat(),
        'missed_prior_window': False,
        'username': 'fixture-private-identity',
        'ip_address': '192.0.2.1',
        'target_user_id': 42,
    })
    return {'state': 'fresh', 'payload': payload}


def test_catalog_and_policy_remain_reserved() -> None:
    rule = policies.catalog_rule(auth.RULE_KEY)
    assert rule is not None
    assert rule['status'] == 'reserved' and rule['domain'] == 'authentication'
    assert not rule['risk_exception']['enabled']
    override = Mock(eligible=True, mode='automatic')
    policy = policies.effective_alert_policy(auth.RULE_KEY, override=override, observed_severity='critical')
    assert not policy['eligible']
    with pytest.raises(ValueError, match='not qualified'):
        policies.upsert_recommendation_alert_policy(
            rule_key=auth.RULE_KEY, eligible=True, mode='automatic',
            stability_window_minutes=0, minimum_occurrences=1, grouping_mode='finding', actor_user_id=1,
        )


def test_candidate_allowlist_and_quiet_observation() -> None:
    evidence = auth.qualified_abuse_evidence(_snapshot(), now=NOW)
    assert evidence is not None and evidence['asset_key'] == 'local-deployment'
    assert evidence['indicators'] == ['recovery_principal_rejection_pattern']
    assert evidence['attack_confirmed'] is False
    assert not {'username', 'ip_address', 'target_user_id'} & evidence.keys()
    assert 'fixture-private-identity' not in str(evidence) and '192.0.2.1' not in str(evidence)
    quiet = auth.qualified_abuse_evidence(_snapshot(positive=False), now=NOW)
    assert quiet is not None and quiet['indicators'] == []


@pytest.mark.parametrize('state', ('disabled', 'missing', 'partial', 'stale', 'unavailable'))
def test_unqualified_states_are_not_quiet(state: str) -> None:
    snapshot = _snapshot()
    snapshot['state'] = state
    assert auth.qualified_abuse_evidence(snapshot, now=NOW) is None


@pytest.mark.parametrize('key,value', (
    ('schema_version', True), ('coverage', 'partial'), ('source_authority', 'unknown'),
    ('missed_prior_window', True), ('sample_rows', 2001), ('credential_rejections', -1),
    ('known_targets', 100), ('peak_current_recovery_principal_rejections', 999),
    ('indicators', ['unknown']), ('window_start', 'invalid'),
))
def test_invalid_candidate_fails_closed(key: str, value: object) -> None:
    snapshot = _snapshot()
    snapshot['payload'][key] = value
    assert auth.qualified_abuse_evidence(snapshot, now=NOW) is None


def test_previous_window_rejected_even_if_snapshot_reports_fresh() -> None:
    assert auth.qualified_abuse_evidence(_snapshot(), now=NOW + timedelta(minutes=15)) is None


def test_reserved_and_worker_path_do_not_read_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    read = Mock()
    monkeypatch.setattr(auth, 'read_authentication_abuse_signal', read)
    rule = policies.catalog_rule(auth.RULE_KEY)
    assert rule is not None
    assert auth.build_authentication_recommendation_findings({auth.RULE_KEY: rule}) == []
    candidate_rule = {**rule, 'status': 'available'}
    assert auth.build_authentication_recommendation_findings({auth.RULE_KEY: candidate_rule}) == []
    read.assert_not_called()


@pytest.mark.parametrize('authorized', (False, True))
def test_candidate_requires_protected_request(monkeypatch: pytest.MonkeyPatch, authorized: bool) -> None:
    app = Flask(__name__)
    actor = SimpleNamespace(
        is_authenticated=True, is_active=True, auth_source='database',
        is_super_admin=authorized, has_permission=lambda key: key == 'intelligence.view',
    )
    monkeypatch.setattr(auth, 'current_user', actor)
    read = Mock(return_value=_snapshot())
    monkeypatch.setattr(auth, 'read_authentication_abuse_signal', read)
    monkeypatch.setattr(auth, 'datetime', SimpleNamespace(now=lambda _tz: NOW, fromisoformat=datetime.fromisoformat))
    rule = policies.catalog_rule(auth.RULE_KEY)
    assert rule is not None
    with app.test_request_context('/fixture'):
        candidate = auth.build_authentication_recommendation_findings({
            auth.RULE_KEY: {**rule, 'status': 'available'},
        })
    if authorized:
        assert len(candidate) == 1 and candidate[0]['rule_key'] == auth.FINDING_KEY
        read.assert_called_once()
    else:
        assert not candidate
        read.assert_not_called()


def test_case_mutation_source_recovery_and_delivery_are_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    case = Mock(domain='authentication', source_type='recommendation')
    for asset_key in ('', 'local-deployment', 'foreign-deployment'):
        assert recommendation_source._source_evidence_posture(
            domain='authentication', asset_key=asset_key, signal_source='authentication_committed_evidence',
        ) == (False, 'source_unavailable')
    assert routing.matching_routing_policies(case) == []
    assert routing.firing_routes(case) == []
    assert not routing.policy_allows_resolved(case, 1)
    assert notifications._dispatch_firing(case)['skipped'] == 1
    assert notifications._dispatch_resolved(case)['skipped'] == 1
    assert notifications._deliver_case_event(case, channel_id=1, event_state='firing', sequence='fixture') == {
        'successful': 0, 'failed': 0, 'skipped': 1,
    }
    monkeypatch.setattr(application, 'get_case', lambda _id: case)
    operation = Mock()
    assert application.apply_case_mutation('fixture', operation=operation) is None
    operation.assert_not_called()
