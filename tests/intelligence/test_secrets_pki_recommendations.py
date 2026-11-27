"""HV-11 bounded PKI population-wide Intelligence recommendation contracts."""

from datetime import UTC, datetime

import pytest

from app.intelligence import secrets_pki_recommendations as evaluator


def _rules():
    return {
        'secrets_pki.pki.stored_certificate_expiry_pressure': {
            'rule_key': 'secrets_pki.pki.stored_certificate_expiry_pressure',
            'domain': 'secrets_pki',
            'source_kind': 'pki_certificate_population',
            'severity': 'warning',
            'priority': 'P2',
            'status': 'available',
        }
    }


def _snapshot(*, expired=0, soon=0, later=0, status='ready'):
    within = soon + later + 2
    return {
        'status': status,
        'observed_stored_certificates': within + expired,
        'within_validity_window': within,
        'not_yet_valid': 0,
        'expired': expired,
        'unknown': 0,
        'expires_within_7d': soon,
        'expires_8_to_30d': later,
        'expires_after_30d': 2,
        'last_observed_at': datetime(2026, 10, 23, tzinfo=UTC),
    }


@pytest.mark.parametrize(
    ('expired', 'soon', 'later', 'expected_severity', 'expected_priority'),
    [
        (1, 0, 0, 'critical', 'P1'),
        (0, 1, 0, 'warning', 'P2'),
        (0, 0, 1, 'info', 'P3'),
    ],
)
def test_qualified_population_pressure_uses_single_canonical_finding(
    monkeypatch,
    expired,
    soon,
    later,
    expected_severity,
    expected_priority,
):
    monkeypatch.setattr(
        evaluator,
        'build_stored_pki_validity_posture',
        lambda: _snapshot(expired=expired, soon=soon, later=later),
    )
    rows = evaluator.build_secrets_pki_recommendation_findings(_rules())
    assert len(rows) == 1
    finding = rows[0]
    assert finding['severity'] == expected_severity
    assert finding['priority'] == expected_priority
    assert finding['rule_key'].endswith(':population')
    assert finding['evidence']['asset_key'] == 'secrets_pki:stored_public_certificates'
    assert not any(
        key in str(finding['evidence']).lower()
        for key in ('mount', 'namespace', 'serial', 'fingerprint', 'token', 'secretid')
    )


@pytest.mark.parametrize(
    'status',
    ['not_configured', 'incomplete', 'blocked', 'unavailable', 'stale'],
)
def test_unqualified_source_does_not_create_finding(monkeypatch, status):
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: _snapshot(expired=3, status=status))
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []


def test_qualified_no_expiry_pressure_is_not_actionable(monkeypatch):
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', _snapshot)
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []


def test_inconsistent_population_count_is_rejected(monkeypatch):
    malformed = _snapshot(expired=1)
    malformed['observed_stored_certificates'] = 999
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: malformed)
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []


def test_missing_timestamp_or_count_is_rejected(monkeypatch):
    invalid = _snapshot(expired=1)
    invalid['last_observed_at'] = None
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: invalid)
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []
    invalid['last_observed_at'] = datetime(2026, 10, 23)
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []
    invalid['expired'] = None
    assert evaluator.build_secrets_pki_recommendation_findings(_rules()) == []


def test_absent_rule_skips_source_read(monkeypatch):
    def denied():
        raise AssertionError('Must not query committed evidence for unrelated rule')

    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', denied)
    assert evaluator.build_secrets_pki_recommendation_findings({}) == []


def test_intelligence_gate_denies_actorless_context(monkeypatch):
    from app.intelligence import service

    monkeypatch.setattr(service, 'has_request_context', lambda: False)
    assert service._can_view_secrets_pki_intelligence() is False


@pytest.mark.parametrize(
    ('intelligence', 'secrets', 'allowed'),
    [
        (True, True, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ],
)
def test_intelligence_gate_requires_both_permissions(monkeypatch, intelligence, secrets, allowed):
    from types import SimpleNamespace

    from app.intelligence import service

    monkeypatch.setattr(service, 'has_request_context', lambda: True)
    monkeypatch.setattr(
        service,
        'current_user',
        SimpleNamespace(
            is_authenticated=True,
            has_permission=lambda permission: intelligence if permission == 'intelligence.view' else secrets,
        ),
    )
    assert service._can_view_secrets_pki_intelligence() is allowed


def _validity_rules():
    rules = _rules()
    key = 'secrets_pki.pki.stored_certificate_validity_review'
    rules[key] = {
        'rule_key': key,
        'domain': 'secrets_pki',
        'source_kind': 'pki_certificate_population',
        'severity': 'warning',
        'priority': 'P2',
        'status': 'available',
        'alert_escalation': {'eligible': False},
        'risk_exception': {'enabled': False},
    }
    return rules


@pytest.mark.parametrize('expired', [0, 1])
def test_qualified_unknown_validity_is_independent_of_expiry(monkeypatch, expired):
    snapshot = _snapshot(expired=expired)
    snapshot['unknown'] = 2
    snapshot['observed_stored_certificates'] += 2
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    findings = evaluator.build_secrets_pki_recommendation_findings(_validity_rules())
    assert len(findings) == 1 + expired
    review = findings[-1]
    assert review['rule_key'] == 'secrets_pki.pki.stored_certificate_validity_review:population'
    assert review['severity'] == 'warning'
    assert review['priority'] == 'P2'
    assert review['alert_escalation']['eligible'] is False
    assert review['risk_exception']['enabled'] is False
    assert review['evidence']['unclassified_validity_windows'] == 2
    assert review['evidence']['trust_verified'] is False
    assert review['evidence']['endpoint_serving_verified'] is False
    if expired:
        assert findings[0]['severity'] == 'critical'


def test_future_dated_certificates_are_not_unknown_validity(monkeypatch):
    snapshot = _snapshot()
    snapshot['not_yet_valid'] = 3
    snapshot['observed_stored_certificates'] += 3
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    assert evaluator.build_secrets_pki_recommendation_findings(_validity_rules()) == []


@pytest.mark.parametrize('status', ['incomplete', 'not_configured', 'blocked', 'unavailable', 'stale'])
def test_unknown_validity_does_not_override_unqualified_source(monkeypatch, status):
    snapshot = _snapshot(status=status)
    snapshot['unknown'] = 2
    snapshot['observed_stored_certificates'] += 2
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    assert evaluator.build_secrets_pki_recommendation_findings(_validity_rules()) == []


def test_unknown_validity_count_must_reconcile(monkeypatch):
    snapshot = _snapshot()
    snapshot['unknown'] = 2
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    assert evaluator.build_secrets_pki_recommendation_findings(_validity_rules()) == []


def test_validity_rule_can_be_selected_independently(monkeypatch):
    snapshot = _snapshot(expired=1)
    snapshot['unknown'] = 1
    snapshot['observed_stored_certificates'] += 1
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    rules = _validity_rules()
    rules.pop('secrets_pki.pki.stored_certificate_expiry_pressure')
    findings = evaluator.build_secrets_pki_recommendation_findings(rules)
    assert len(findings) == 1
    assert findings[0]['rule_key'] == 'secrets_pki.pki.stored_certificate_validity_review:population'


@pytest.mark.parametrize('status', ['not_configured', 'incomplete', 'blocked', 'unavailable', 'stale', 'ready'])
def test_population_readiness_uses_same_evaluation_generation(monkeypatch, status):
    calls = []

    def read():
        calls.append(True)
        return _snapshot(status=status)

    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', read)
    readiness = {}
    assert evaluator.build_secrets_pki_recommendation_findings(_rules(), readiness=readiness) == []
    assert readiness == {'status': status}
    assert len(calls) == 1


def test_invalid_ready_population_is_not_qualified(monkeypatch):
    snapshot = _snapshot(expired=2)
    snapshot['observed_stored_certificates'] += 1
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', lambda: snapshot)
    readiness = {}
    assert evaluator.build_secrets_pki_recommendation_findings(_rules(), readiness=readiness) == []
    assert readiness == {'status': 'unavailable'}


def test_population_readiness_remains_unset_without_scope(monkeypatch):
    from app.intelligence import service

    monkeypatch.setattr(service, '_can_view_secrets_pki_intelligence', lambda: False)

    def denied():
        pytest.fail('Unauthorized actor must not read population evidence')

    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', denied)
    readiness = {}
    assert service._build_recommendation_findings(list(_rules().values()), pki_readiness=readiness) == []
    assert readiness == {}


def test_authorized_population_evaluation_propagates_readiness(monkeypatch):
    from app.intelligence import service

    monkeypatch.setattr(service, '_can_view_secrets_pki_intelligence', lambda: True)
    monkeypatch.setattr(evaluator, 'build_stored_pki_validity_posture', _snapshot)
    readiness = {}
    assert service._build_recommendation_findings(list(_rules().values()), pki_readiness=readiness) == []
    assert readiness == {'status': 'ready'}
