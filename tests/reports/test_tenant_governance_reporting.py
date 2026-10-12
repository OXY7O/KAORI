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



def test_tenant_findings_reject_cross_cluster_and_cross_namespace(monkeypatch) -> None:
    from app.reports.export.payloads import tenant_governance as module

    observed = []

    def findings(*, domain: str, asset_key: str) -> list[dict]:
        observed.append((domain, asset_key))
        return [
            {
                'rule_key': 'kubernetes.tenant.access.grant_drift',
                'evidence': {'tenant_id': 'tenant-1', 'namespace': 'selected'},
            },
            {
                'rule_key': 'kubernetes.tenant.access.grant_drift',
                'evidence': {'tenant_id': 'tenant-1', 'namespace': 'another'},
            },
            {
                'rule_key': 'kubernetes.tenant.credential.expired',
                'evidence': {'tenant_id': 'tenant-2'},
            },
            {
                'rule_key': 'kubernetes.tenant.provider.degraded',
                'evidence': {'tenant_id': 'tenant-1'},
            },
            {'rule_key': 'kubernetes.tenant.provider.degraded', 'evidence': {'cluster_id': 'cluster-1'}},
        ]

    monkeypatch.setattr(module, 'get_active_recommendation_findings', findings)
    rows = module._tenant_findings(
        'cluster-1', namespace='selected', tenant_ids={'tenant-1'}
    )
    assert observed == [('kubernetes', 'cluster-1')]
    assert len(rows) == 2
    assert {row['rule_key'] for row in rows} == {
        'kubernetes.tenant.access.grant_drift',
        'kubernetes.tenant.provider.degraded',
    }


def test_cluster_wide_tenant_findings_keep_eligible_cluster_evidence(monkeypatch) -> None:
    from app.reports.export.payloads import tenant_governance as module

    monkeypatch.setattr(
        module,
        'get_active_recommendation_findings',
        lambda **kwargs: [
            {'rule_key': 'kubernetes.tenant.access.grant_drift', 'evidence': {'cluster_id': kwargs['asset_key']}},
            {'rule_key': 'kubernetes.node.capacity', 'evidence': {'cluster_id': kwargs['asset_key']}},
        ],
    )
    rows = module._tenant_findings('cluster-1')
    assert len(rows) == 1
    assert rows[0]['rule_key'] == 'kubernetes.tenant.access.grant_drift'
