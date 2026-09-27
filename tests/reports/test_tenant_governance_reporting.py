from types import SimpleNamespace

from app.reports.export.payloads.tenant_governance import (
    credential_row,
    recommendation_row,
)


def test_credential_row_contains_metadata_only() -> None:
    credential = SimpleNamespace(
        public_id='cred-1',
        tenant=SimpleNamespace(name='payments'),
        owner_user=SimpleNamespace(username='alice'),
        credential_type='human_service_account',
        purpose='operations',
        application_name=None,
        delivery_method='jumpserver',
        status='active',
        reconciliation_status='ready',
        service_account_name='kaori-alice',
        jumpserver_reference='jumpserver://asset/123',
        renewal_due_at=None,
        valid_until=None,
        rotation_generation=2,
        last_reconciled_at=None,
    )
    row = credential_row(credential)
    assert row['credential_id'] == 'cred-1'
    assert row['owner'] == 'alice'
    assert row['delivery_method'] == 'jumpserver'
    assert 'token' not in row
    assert 'kubeconfig' not in row
    assert 'private_key' not in row


def test_recommendation_row_preserves_rule_and_evidence_scope() -> None:
    row = recommendation_row(
        {
            'rule_key': 'kubernetes.tenant.access.grant_drift:grant-1',
            'title': 'Access drift',
            'severity': 'critical',
            'priority': 'P1',
            'summary': 'Grant differs from intent.',
            'recommended_action': 'Reconcile the grant.',
            'evidence': {'tenant_id': 'tenant-1', 'namespace': 'payments'},
        }
    )
    assert row['rule_key'].startswith('kubernetes.tenant.')
    assert row['severity'] == 'critical'
    assert row['tenant_id'] == 'tenant-1'
    assert row['namespace'] == 'payments'
