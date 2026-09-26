from datetime import UTC, datetime

from app.kubernetes.tenant.audit_correlation import (
    TenantAuditPrincipalCandidate,
    correlate_audit_principal,
    normalize_kubernetes_audit_event,
)


def _event(**overrides):
    event = {
        'auditID': 'audit-123',
        'stageTimestamp': '2026-09-27T01:02:03Z',
        'verb': 'patch',
        'user': {
            'username': 'system:serviceaccount:payments-prod:kaori-deploy-payments-prod',
            'groups': ['system:serviceaccounts', 'system:authenticated'],
        },
        'objectRef': {
            'apiGroup': 'apps',
            'apiVersion': 'v1',
            'resource': 'deployments',
            'namespace': 'payments-prod',
            'name': 'payment-api',
        },
        'responseStatus': {'code': 200, 'status': 'Success'},
        'requestObject': {'data': {'token': 'must-not-survive'}},
        'responseObject': {'stringData': {'password': 'must-not-survive'}},
    }
    event.update(overrides)
    return event


def test_normalization_keeps_correlation_fields_and_drops_payload_bodies() -> None:
    normalized = normalize_kubernetes_audit_event(_event(), source_id='audit-file-a', retention_days=30)

    assert normalized.event_uid == 'audit-123'
    assert normalized.username == 'system:serviceaccount:payments-prod:kaori-deploy-payments-prod'
    assert normalized.service_account_namespace == 'payments-prod'
    assert normalized.service_account_name == 'kaori-deploy-payments-prod'
    assert normalized.namespace == 'payments-prod'
    assert normalized.resource == 'deployments'
    assert normalized.verb == 'patch'
    assert normalized.outcome == 'success'
    assert normalized.response_code == 200
    assert normalized.expires_at > datetime.now(UTC)
    rendered = repr(normalized)
    assert 'must-not-survive' not in rendered
    assert 'requestObject' not in rendered
    assert 'responseObject' not in rendered


def test_normalization_builds_stable_uid_when_audit_id_is_missing() -> None:
    first = normalize_kubernetes_audit_event(
        _event(auditID=None),
        source_id='audit-file-a',
        retention_days=30,
    )
    second = normalize_kubernetes_audit_event(
        _event(auditID=None),
        source_id='audit-file-a',
        retention_days=30,
    )
    assert first.event_uid == second.event_uid


def test_managed_service_account_maps_to_credential_owner() -> None:
    normalized = normalize_kubernetes_audit_event(_event(), source_id='audit-file-a', retention_days=30)
    candidate = TenantAuditPrincipalCandidate(
        tenant_id='tenant-a',
        tenant_environment_id=3,
        tenant_namespace_id=9,
        namespace='payments-prod',
        principal_kind='service_account',
        subject_name='kaori-deploy-payments-prod',
        membership_id=11,
        access_grant_id=12,
        credential_id=13,
        credential_status='active',
    )
    result = correlate_audit_principal(normalized, [candidate])
    assert result.status == 'managed'
    assert result.credential_id == 13
    assert result.access_grant_id == 12


def test_revoked_managed_credential_remains_attributable() -> None:
    normalized = normalize_kubernetes_audit_event(_event(), source_id='audit-file-a', retention_days=30)
    candidate = TenantAuditPrincipalCandidate(
        tenant_id='tenant-a',
        tenant_environment_id=3,
        tenant_namespace_id=9,
        namespace='payments-prod',
        principal_kind='service_account',
        subject_name='kaori-deploy-payments-prod',
        credential_id=13,
        credential_status='revoked',
    )
    result = correlate_audit_principal(normalized, [candidate])
    assert result.status == 'managed_revoked'
    assert result.credential_id == 13


def test_unknown_and_ambiguous_principals_are_explicit() -> None:
    normalized = normalize_kubernetes_audit_event(_event(), source_id='audit-file-a', retention_days=30)
    assert correlate_audit_principal(normalized, []).status == 'unmanaged'

    candidate = TenantAuditPrincipalCandidate(
        tenant_id='tenant-a',
        tenant_environment_id=3,
        tenant_namespace_id=9,
        namespace='payments-prod',
        principal_kind='service_account',
        subject_name='kaori-deploy-payments-prod',
        credential_id=13,
        credential_status='active',
    )
    other = TenantAuditPrincipalCandidate(
        tenant_id='tenant-b',
        tenant_environment_id=4,
        tenant_namespace_id=10,
        namespace='payments-prod',
        principal_kind='service_account',
        subject_name='kaori-deploy-payments-prod',
        credential_id=14,
        credential_status='active',
    )
    assert correlate_audit_principal(normalized, [candidate, other]).status == 'ambiguous'
