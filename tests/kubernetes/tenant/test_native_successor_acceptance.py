"""External Native successor consent is provider-authenticated and plan-bound."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import native_successor_acceptance as acceptance
from app.kubernetes.tenant import native_successor_identity as identity
from app.kubernetes.tenant.release_handoff_approval import _plan_hash


def plan():
    data = {
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 2, 'provider': 'native_kubernetes',
        'requested_by': 42, 'requested_at': datetime.now(UTC).isoformat(),
        'successor_owner': 'platform-team', 'change_reference': 'CHG-2026-002',
        'handoff_fingerprint': 'exact-hash',
        'provider_identity': [
            {'kind': 'Namespace', 'name': 'dev', 'uid': 'uid-a', 'resource_version': '7'},
        ],
        'handoff_components': [{
            'kind': 'Namespace', 'namespace': 'dev', 'name': 'dev',
            'uid': 'uid-a', 'resource_version': '7', 'handoff': 'external_acceptance_required',
            'ownership': 'kaori_marker_correlated',
        }, {
            'kind': 'ResourceQuota', 'namespace': 'dev', 'name': 'limits',
            'uid': 'uid-b', 'resource_version': '9', 'handoff': 'external_acceptance_required',
            'ownership': 'kaori_marker_correlated',
        }],
    }
    data['plan_sha256'] = _plan_hash(data)
    return data


class Provider:
    def __init__(self, *, allow=True):
        self.calls = []
        self.allow = allow

    def authentication_api(self):
        return self

    def authorization_api(self):
        return self

    def create_token_review(self, body, **kwargs):
        assert kwargs['_request_timeout'] == 5
        self.calls.append(('token', body.spec.token))
        return SimpleNamespace(status=SimpleNamespace(
            authenticated=True, error=None, audiences=['kubernetes'],
            user=SimpleNamespace(
                username='succ-user', uid='principal-uid',
                groups=['platform-team', 'system:authenticated'],
            ),
        ))

    def create_subject_access_review(self, body, **kwargs):
        assert kwargs['_request_timeout'] == 5
        assert body.spec.user == 'succ-user'
        assert body.spec.uid == 'principal-uid'
        self.calls.append(('sar', body.spec.resource_attributes))
        return SimpleNamespace(status=SimpleNamespace(
            allowed=self.allow, denied=not self.allow, evaluation_error=None,
        ))


def test_token_review_and_sar_require_exact_resource_rbac(monkeypatch):
    provider = Provider()
    monkeypatch.setattr(identity.runtime_adapter, 'build_client', lambda _: provider)
    result = identity.verify_native_successor_resource_authority(
        cluster=SimpleNamespace(
            id='cluster-a', kubernetes_connection=SimpleNamespace(verify_ssl=True),
        ),
        plan=plan(), provider_token='one-time-provider-token',
    )
    assert result['scope_count'] == 2
    assert result['consent_verified'] is False
    assert result['resource_authority_verified'] is True
    assert len([c for c in provider.calls if c[0] == 'sar']) == 4
    attrs = [call[1] for call in provider.calls if call[0] == 'sar']
    assert {(a.resource, a.verb, a.namespace) for a in attrs} == {
        ('namespaces', 'get', None), ('namespaces', 'patch', None),
        ('resourcequotas', 'get', 'dev'), ('resourcequotas', 'patch', 'dev'),
    }
    assert 'one-time-provider-token' not in str(result)


def test_denied_sar_cannot_promote_successor_identity_to_consent(monkeypatch):
    provider = Provider(allow=False)
    monkeypatch.setattr(identity.runtime_adapter, 'build_client', lambda _: provider)
    with pytest.raises(ValueError, match='authorization'):
        identity.verify_native_successor_resource_authority(
            cluster=SimpleNamespace(
                id='cluster-a', kubernetes_connection=SimpleNamespace(verify_ssl=True),
            ),
            plan=plan(), provider_token='token',
        )


def test_approval_boundary_never_accepts_unauthenticated_reference():
    p = plan()
    reviewer = {
        'approved_by': 43,
    }
    from app.kubernetes.tenant import native_successor_acceptance as service
    service.latest_native_successor_acceptance = lambda _: {
        'status': 'external_reference_unverified', 'plan_sha256': p['plan_sha256'],
    }
    with pytest.raises(ValueError, match='verified successor consent'):
        service.require_current_native_acceptance(tenant_id='tenant-a', plan=p, approval=reviewer)


def test_explicit_confirm_is_required_before_provider_requests():
    with pytest.raises(ValueError, match='explicitly accept'):
        acceptance.accept_native_successor_handoff_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='a' * 64, provider_token='not-consumed', confirmed=False,
        )


def test_plan_acceptance_receipt_requires_exact_fingerprint_and_freshness(monkeypatch):
    p = plan()
    reviewer = {'approved_by': 43}
    receipt = {
        'status': 'verified_explicit_successor_acceptance',
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 2, 'plan_sha256': p['plan_sha256'],
        'handoff_fingerprint': p['handoff_fingerprint'],
        'provider_identity': p['provider_identity'],
        'successor_owner': 'platform-team',
        'reviewed_by': 43, 'authenticated_provider': 'kubernetes_token_review',
        'resource_authority_verified': True, 'consent_verified': True,
        'secret_material_persisted': False,
        'accepted_at': datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(acceptance, 'latest_native_successor_acceptance', lambda _: receipt)
    assert acceptance.require_current_native_acceptance(
        tenant_id='tenant-a', plan=p, approval=reviewer,
    )['consent_verified']
    receipt['handoff_fingerprint'] = 'foreign'
    with pytest.raises(ValueError):
        acceptance.require_current_native_acceptance(
            tenant_id='tenant-a', plan=p, approval=reviewer,
        )
