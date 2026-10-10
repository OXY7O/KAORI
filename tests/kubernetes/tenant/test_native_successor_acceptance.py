"""Platform Admin approval and X.509 provider identity stay separate authorities."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import native_platform_admin_authority as authority
from app.kubernetes.tenant import native_successor_acceptance as acceptance
from app.kubernetes.tenant.release_handoff_approval import _plan_hash


def _plan():
    data = {
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a', 'generation': 2,
        'provider': 'native_kubernetes',
        'requested_by': 42, 'requested_at': datetime.now(UTC).isoformat(),
        'successor_owner': 'platform-team', 'change_reference': 'CHG-123',
        'handoff_fingerprint': 'exact-fingerprint',
        'provider_identity': [
            {'kind': 'Namespace', 'name': 'dev', 'uid': 'uid-a', 'resource_version': '7'},
        ],
        'handoff_components': [
            {'kind': 'Namespace', 'name': 'dev', 'namespace': 'dev',
             'uid': 'uid-a', 'resource_version': '7',
             'handoff': 'external_acceptance_required',
             'ownership': 'kaori_marker_correlated'},
        ],
    }
    data['plan_sha256'] = _plan_hash(data)
    return data


class _Provider:
    def __init__(self, *, allowed=True):
        self.allowed = allowed
        self.calls = []

    def authentication_api(self):
        return self

    def authorization_api(self):
        return self

    def create_self_subject_review(self, body, **kwargs):
        self.calls.append('identity')
        assert kwargs['_request_timeout'] == 5
        return SimpleNamespace(status=SimpleNamespace(user_info=SimpleNamespace(
            username='kubernetes-admin',
            groups=['kubeadm:cluster-admins', 'system:authenticated'],
            extra={'authentication.kubernetes.io/credential-id': ['X509SHA256=test-hash']},
        )))

    def create_self_subject_access_review(self, body, **kwargs):
        self.calls.append((body.spec.resource_attributes.resource, body.spec.resource_attributes.verb))
        assert kwargs['_request_timeout'] == 5
        return SimpleNamespace(status=SimpleNamespace(
            allowed=self.allowed, denied=not self.allowed, evaluation_error=None,
        ))


def _cluster(*, tls=True):
    return SimpleNamespace(
        id='cluster-a', kubernetes_connection=SimpleNamespace(verify_ssl=tls),
    )


def test_provider_kubeconfig_identity_and_exact_scoped_rbac(monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(authority.runtime_adapter, 'build_client', lambda _: provider)
    evidence = authority.verify_native_provider_admin_authority(
        cluster=_cluster(), components=_plan()['handoff_components'],
    )
    assert evidence['provider_username'] == 'kubernetes-admin'
    assert evidence['provider_credential_id'] == 'X509SHA256=test-hash'
    assert evidence['scope_count'] == 1
    assert provider.calls == ['identity', ('namespaces', 'get'), ('namespaces', 'patch')]
    assert evidence['resource_authority_verified'] is True
    assert evidence['secret_material_persisted'] is False
    assert not evidence.get('consent_verified')


def test_denied_provider_permission_is_blocked(monkeypatch):
    monkeypatch.setattr(
        authority.runtime_adapter, 'build_client', lambda _: _Provider(allowed=False),
    )
    with pytest.raises(ValueError, match='lacks get permission'):
        authority.verify_native_provider_admin_authority(
            cluster=_cluster(), components=_plan()['handoff_components'],
        )


def test_tls_off_is_blocked_before_provider_call():
    with pytest.raises(ValueError, match='Verified Kubernetes TLS'):
        authority.verify_native_provider_admin_authority(
            cluster=_cluster(tls=False), components=_plan()['handoff_components'],
        )


def test_unknown_or_duplicate_scope_is_blocked():
    plan = _plan()
    with pytest.raises(ValueError, match='duplicated'):
        authority.verify_native_provider_admin_authority(
            cluster=_cluster(), components=plan['handoff_components'] * 2,
        )


def test_explicit_platform_admin_confirmation_is_required_before_reads():
    with pytest.raises(ValueError, match='Explicit Platform Admin'):
        acceptance.accept_native_successor_handoff_committed(
            tenant_id='tenant-a', actor_user_id=43, plan_sha256='a' * 64,
            confirmed=False,
        )


def test_historical_bearer_token_approval_cannot_unlock_new_governance(monkeypatch):
    p = _plan()
    old = {
        'status': 'verified_explicit_successor_acceptance',
        'plan_sha256': p['plan_sha256'], 'tenant_id': 'tenant-a',
        'consent_verified': True,
    }
    monkeypatch.setattr(acceptance, 'latest_native_successor_acceptance', lambda _: old)
    with pytest.raises(ValueError, match='Platform Admin acceptance'):
        acceptance.require_current_native_acceptance(
            tenant_id='tenant-a', plan=p, approval={'approved_by': 43},
        )


def test_platform_admin_receipt_bound_to_exact_plan_and_provider_identity(monkeypatch):
    p = _plan()
    accepted = {
        'status': 'platform_admin_handoff_accepted', 'authority_mode': 'platform_admin_governed',
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a', 'generation': 2,
        'plan_sha256': p['plan_sha256'], 'handoff_fingerprint': p['handoff_fingerprint'],
        'provider_identity': p['provider_identity'],
        'successor_owner': p['successor_owner'],
        'reviewed_by': 43, 'verified_provider_identity': True,
        'resource_authority_verified': True, 'consent_verified': True,
        'secret_material_persisted': False, 'accepted_at': datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(acceptance, 'latest_native_successor_acceptance', lambda _: accepted)
    assert acceptance.require_current_native_acceptance(
        tenant_id='tenant-a', plan=p, approval={'approved_by': 43},
    ) == accepted
    accepted['provider_identity'] = []
    with pytest.raises(ValueError, match='Platform Admin acceptance'):
        acceptance.require_current_native_acceptance(
            tenant_id='tenant-a', plan=p, approval={'approved_by': 43},
        )


def test_platform_admin_human_requires_all_three_existing_permissions(monkeypatch):
    actor = SimpleNamespace(has_permission=lambda value: value != 'clusters.manage')
    monkeypatch.setattr(
        authority.db, 'session',
        SimpleNamespace(get=lambda _model, _id: actor),
    )
    with pytest.raises(ValueError, match='Platform Admin permissions'):
        authority.require_platform_admin_actor(43)


def test_valid_existing_platform_admin_permissions_are_accepted(monkeypatch):
    actor = SimpleNamespace(has_permission=lambda _: True)
    monkeypatch.setattr(
        authority.db, 'session',
        SimpleNamespace(get=lambda _model, _id: actor),
    )
    authority.require_platform_admin_actor(43)
