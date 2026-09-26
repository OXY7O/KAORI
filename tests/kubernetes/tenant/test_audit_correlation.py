from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.audit_correlation import (
    CorrelationCandidate,
    TenantAuditNormalizationError,
    choose_correlation_candidate,
    normalize_kubernetes_audit_event,
    service_account_identity,
)


def _audit_event(**overrides):
    event = {
        'auditID': 'audit-123',
        'verb': 'patch',
        'stageTimestamp': '2026-09-27T01:02:03Z',
        'user': {
            'username': 'system:serviceaccount:payments-prod:kaori-payments-deploy',
            'groups': ['system:serviceaccounts', 'system:authenticated'],
        },
        'objectRef': {
            'apiGroup': 'apps',
            'apiVersion': 'v1',
            'resource': 'deployments',
            'namespace': 'payments-prod',
            'name': 'api',
        },
        'responseStatus': {'code': 200, 'status': 'Success'},
        'requestObject': {'data': {'token': 'must-not-persist'}},
        'responseObject': {'metadata': {'managedFields': ['large-payload']}},
        'sourceIPs': ['10.0.0.2'],
    }
    event.update(overrides)
    return event


def test_normalizer_keeps_only_bounded_safe_evidence() -> None:
    record = normalize_kubernetes_audit_event(_audit_event(), source_reference='s3://audit/2026/09/27/1.json')
    payload = record.as_dict()

    assert record.source_event_id == 'audit-123'
    assert record.namespace == 'payments-prod'
    assert record.resource == 'deployments'
    assert record.verb == 'patch'
    assert record.response_code == 200
    assert record.outcome == 'success'
    assert record.event_at == datetime(2026, 9, 27, 1, 2, 3, tzinfo=UTC)
    assert payload['source_reference'] == 's3://audit/2026/09/27/1.json'
    assert 'requestObject' not in repr(payload)
    assert 'responseObject' not in repr(payload)
    assert 'must-not-persist' not in repr(payload)
    assert 'sourceIPs' not in repr(payload)


def test_missing_audit_id_uses_stable_safe_idempotency_key() -> None:
    event = _audit_event()
    event.pop('auditID')
    first = normalize_kubernetes_audit_event(event)
    second = normalize_kubernetes_audit_event(event)
    assert first.idempotency_key == second.idempotency_key
    assert first.source_event_id is None


def test_malformed_source_fails_explicitly() -> None:
    with pytest.raises(TenantAuditNormalizationError, match='principal'):
        normalize_kubernetes_audit_event({'auditID': 'bad', 'verb': 'get'})


def test_service_account_identity_is_strict() -> None:
    assert service_account_identity('system:serviceaccount:payments-prod:robot') == ('payments-prod', 'robot')
    assert service_account_identity('alice@example.com') is None
    assert service_account_identity('system:serviceaccount:missing') is None


def test_single_managed_candidate_is_deterministic_even_when_revoked() -> None:
    candidates = [
        CorrelationCandidate(
            credential_id=8,
            credential_public_id='cred-8',
            credential_status='revoked',
            credential_type='deployer_service_account',
            tenant_id='tenant-a',
            namespace_id=7,
            owner_user_id=11,
            access_grant_id=4,
            application_name='payments-api',
            jumpserver_reference=None,
        )
    ]
    result = choose_correlation_candidate(candidates)
    assert result.status == 'matched'
    assert result.credential_id == 8
    assert result.credential_status == 'revoked'


def test_unknown_and_ambiguous_principals_remain_explicit() -> None:
    unmatched = choose_correlation_candidate([])
    assert unmatched.status == 'unmanaged'

    ambiguous = choose_correlation_candidate(
        [
            CorrelationCandidate(1, 'c1', 'active', 'human_service_account', 'tenant-a', 1, 10, 2, None, 'js-a'),
            CorrelationCandidate(2, 'c2', 'active', 'human_service_account', 'tenant-a', 1, 12, 3, None, 'js-b'),
        ]
    )
    assert ambiguous.status == 'ambiguous'
    assert ambiguous.credential_id is None
