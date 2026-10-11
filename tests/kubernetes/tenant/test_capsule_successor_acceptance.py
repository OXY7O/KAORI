"""#1228 Capsule successor acceptance: X.509, exact independent scope, no provider writes."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import capsule_platform_admin_authority as authority
from app.kubernetes.tenant import capsule_successor_acceptance as acceptance
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint


def _components():
    return [
        {
            'kind': 'CapsuleTenant', 'name': 'kaori-demo', 'uid': 'capsule-uid',
            'resource_version': '7', 'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': 'a' * 64,
        },
        {
            'kind': 'Namespace', 'name': 'kaori-demo-dev', 'namespace': 'kaori-demo-dev',
            'uid': 'namespace-uid', 'resource_version': '11', 'authority': 'capsule',
            'handoff': 'observe_only',
        },
    ]


def _plan():
    components = _components()
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1', 'generation': 2,
        'provider': 'capsule', 'status': 'pending_independent_approval',
        'requested_by': 42, 'requested_at': datetime.now(UTC).isoformat(),
        'successor_owner': 'platform-team', 'change_reference': 'CHG-2026-1234',
        'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'kaori-demo', 'uid': 'capsule-uid', 'resource_version': '7'},
            {'kind': 'Namespace', 'name': 'kaori-demo-dev', 'uid': 'namespace-uid', 'resource_version': '11'},
        ],
        'handoff_components': components,
        'dependency_counts': {
            'credentials': 0, 'Access Grants': 0, 'Memberships': 0,
            'enabled Groups': 0, 'managed resources': 0, 'advanced capabilities': 0,
            'domain reservations': 0, 'exposure policies': 0,
        },
        'blockers': [
            'Capsule allocation was modified by KAORI; explicit provider authority handoff is required.',
        ],
    }
    plan['plan_sha256'] = _plan_hash(plan)
    return plan


def _approval(plan):
    return {
        'status': 'acknowledged_pending_provider_handoff',
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'requested_by': 42, 'approved_by': 43,
        'approved_at': datetime.now(UTC).isoformat(),
        'provider_handoff_verified': False, 'release_authorized': False,
    }


class _Provider:
    def __init__(self, *, allowed=True, credential=True, username='kubernetes-admin'):
        self.allowed = allowed
        self.credential = credential
        self.username = username
        self.calls = []

    def authentication_api(self):
        return self

    def authorization_api(self):
        return self

    def create_self_subject_review(self, body, **kwargs):
        self.calls.append('identity')
        assert kwargs['_request_timeout'] == 5
        extra = (
            {'authentication.kubernetes.io/credential-id': ['X509SHA256=sample']}
            if self.credential else {}
        )
        return SimpleNamespace(status=SimpleNamespace(user_info=SimpleNamespace(
            username=self.username, groups=['system:authenticated'], extra=extra,
        )))

    def create_self_subject_access_review(self, body, **kwargs):
        x = body.spec.resource_attributes
        self.calls.append((x.group, x.resource, x.name, x.namespace, x.verb))
        assert kwargs['_request_timeout'] == 5
        return SimpleNamespace(status=SimpleNamespace(
            allowed=self.allowed, denied=not self.allowed, evaluation_error=None,
        ))


def _cluster(*, tls=True):
    return SimpleNamespace(
        id='cluster-1', kubernetes_connection=SimpleNamespace(verify_ssl=tls),
    )


def test_capsule_provider_authority_verifies_cluster_scoped_cr_and_namespace_get_patch(monkeypatch):
    client = _Provider()
    monkeypatch.setattr(authority.runtime_adapter, 'build_client', lambda _: client)
    evidence = authority.verify_capsule_provider_admin_authority(
        cluster=_cluster(), components=_components(),
    )
    assert client.calls == [
        'identity',
        ('capsule.clastix.io', 'tenants', 'kaori-demo', None, 'get'),
        ('capsule.clastix.io', 'tenants', 'kaori-demo', None, 'patch'),
        ('', 'namespaces', 'kaori-demo-dev', None, 'get'),
        ('', 'namespaces', 'kaori-demo-dev', None, 'patch'),
    ]
    assert evidence['scope_count'] == 2
    assert evidence['provider_credential_id'] == 'X509SHA256=sample'
    assert evidence['provider_mutation_performed'] is False
    assert evidence['secret_material_persisted'] is False


@pytest.mark.parametrize('allowed,credential,username', [
    (False, True, 'kubernetes-admin'),
    (True, False, 'kubernetes-admin'),
    (True, True, 'system:serviceaccount:kaori:worker'),
    (True, True, 'system:node:kubelet'),
])
def test_capsule_provider_rejects_denied_rbac_missing_x509_or_serviceaccount(
    monkeypatch, allowed, credential, username,
):
    client = _Provider(allowed=allowed, credential=credential, username=username)
    monkeypatch.setattr(authority.runtime_adapter, 'build_client', lambda _: client)
    with pytest.raises(ValueError, match='authority|principal'):
        authority.verify_capsule_provider_admin_authority(
            cluster=_cluster(), components=_components(),
        )


def test_trusted_system_admin_x509_is_not_mistaken_for_a_service_account(monkeypatch):
    client = _Provider(username='system:admin')
    monkeypatch.setattr(authority.runtime_adapter, 'build_client', lambda _: client)
    evidence = authority.verify_capsule_provider_admin_authority(
        cluster=_cluster(), components=_components(),
    )
    assert evidence['provider_username'] == 'system:admin'
    assert evidence['scope_count'] == 2


def test_capsule_tls_must_be_verified_before_any_provider_request():
    with pytest.raises(ValueError, match='Verified Kubernetes TLS'):
        authority.verify_capsule_provider_admin_authority(
            cluster=_cluster(tls=False), components=_components(),
        )


@pytest.mark.parametrize('mutation', [
    lambda values: values.pop(0),
    lambda values: values.append(dict(values[0])),
    lambda values: values[0].update(capsule_spec_sha256=''),
    lambda values: values[0].update(handoff='observe_only'),
    lambda values: values[1].update(namespace='other'),
    lambda values: values[1].update(uid=''),
    lambda values: values[1].update(kind='ResourceQuota'),
    lambda values: values[1].update(authority='native_kubernetes'),
    lambda values: values[0].update(kind=[]),
])
def test_capsule_authority_rejects_missing_unknown_or_ambiguous_scope(mutation):
    items = _components()
    mutation(items)
    with pytest.raises(ValueError):
        authority._capsule_admin_scope(items)


def test_capsule_receipt_must_be_exact_current_plan_not_a_native_or_old_acceptance(monkeypatch):
    plan = _plan()
    approval = _approval(plan)
    recorded = {
        'status': 'platform_admin_handoff_accepted',
        'authority_mode': 'capsule_platform_admin_governed',
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'provider_identity': plan['provider_identity'],
        'successor_owner': plan['successor_owner'], 'reviewed_by': 43,
        'accepted_by': 44, 'verified_provider_identity': True,
        'resource_authority_verified': True, 'consent_verified': True,
        'authenticated_provider': 'kubernetes_self_subject_review',
        'authorization_source': 'kubernetes_self_subject_access_review',
        'provider_credential_id': 'X509SHA256=sample',
        'secret_material_persisted': False, 'provider_mutation_performed': False,
        'provider_handoff_verified': False, 'release_authorized': False,
        'accepted_at': datetime.now(UTC).isoformat(),
        'scoped_resources': authority._capsule_admin_scope(plan['handoff_components']),
        'scope_count': 2,
    }
    monkeypatch.setattr(acceptance, 'latest_capsule_successor_acceptance', lambda _: recorded)
    assert acceptance.require_current_capsule_acceptance(
        tenant_id=plan['tenant_id'], plan=plan, approval=approval,
    ) is recorded
    for key, value in [
        ('authority_mode', 'platform_admin_governed'),
        ('accepted_by', 42),
        ('consent_verified', False),
        ('provider_credential_id', ''),
        ('provider_credential_id', 'X509SHA256='),
        ('authenticated_provider', 'claimed_by_label'),
        ('provider_handoff_verified', True),
        ('release_authorized', True),
        ('scoped_resources', []),
        ('accepted_at', (datetime.now(UTC)-timedelta(hours=1)).isoformat()),
    ]:
        changed = dict(recorded, **{key: value})
        monkeypatch.setattr(acceptance, 'latest_capsule_successor_acceptance', lambda _, v=changed: v)
        with pytest.raises(ValueError, match='Capsule'):
            acceptance.require_current_capsule_acceptance(
                tenant_id=plan['tenant_id'], plan=plan, approval=approval,
            )


def test_capsule_acceptance_requires_explicit_confirmation_and_fresh_independent_plan(monkeypatch):
    plan = _plan()
    approval = _approval(plan)
    monkeypatch.setattr(acceptance, 'require_platform_admin_actor', lambda _: None)
    monkeypatch.setattr(acceptance, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(acceptance, 'latest_release_handoff_approval', lambda _: approval)
    with pytest.raises(ValueError, match='Explicit'):
        acceptance.accept_capsule_successor_handoff_committed(
            tenant_id='tenant-1', actor_user_id=44,
            plan_sha256=plan['plan_sha256'], confirmed=False,
        )
    for actor, bad_plan, bad_approval in [
        (42, plan, approval),
        (44, dict(plan, provider='native_kubernetes'), approval),
        (44, dict(plan, requested_at=(datetime.now(UTC)-timedelta(hours=1)).isoformat()), approval),
        (44, plan, dict(approval, approved_by=42)),
        (44, plan, dict(approval, status='pending')),
    ]:
        monkeypatch.setattr(acceptance, 'latest_release_handoff_plan', lambda _, v=bad_plan: v)
        monkeypatch.setattr(acceptance, 'latest_release_handoff_approval', lambda _, v=bad_approval: v)
        with pytest.raises(ValueError, match='Capsule Release plan'):
            acceptance.accept_capsule_successor_handoff_committed(
                tenant_id='tenant-1', actor_user_id=actor,
                plan_sha256=plan['plan_sha256'], confirmed=True,
            )


class _Session:
    def __init__(self, tenant, cluster):
        self.tenant, self.cluster = tenant, cluster
        self.events = []
        self.commits = 0

    def get(self, model, key):
        return self.tenant if key == 'tenant-1' else self.cluster

    def add(self, event):
        self.events.append(event)

    def commit(self):
        self.commits += 1


def _bound_service(monkeypatch, *, drift=False, previous=None):
    plan = _plan()
    approval = _approval(plan)
    tenant = SimpleNamespace(
        id='tenant-1', cluster_id='cluster-1', generation=2,
        ownership_status='adopted', lifecycle_status='ready',
        provider_key='capsule', provider_state='capsule',
        reconciliation_authority='capsule', provider_reference='kaori-demo',
    )
    cluster = _cluster()
    session = _Session(tenant, cluster)

    class _Query:
        def filter_by(self, **_):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return tenant

    monkeypatch.setattr(acceptance, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(acceptance, 'Tenant', SimpleNamespace(query=_Query()))
    monkeypatch.setattr(acceptance, 'Cluster', type('ClusterPlaceholder', (), {}))
    monkeypatch.setattr(acceptance, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(acceptance, 'require_platform_admin_actor', lambda _: None)
    monkeypatch.setattr(acceptance, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(acceptance, 'latest_release_handoff_approval', lambda _: approval)
    monkeypatch.setattr(acceptance, 'latest_capsule_successor_acceptance', lambda _: previous)
    fresh = {
        **plan, 'status': 'blocked',
        'live_provider_identity': plan['provider_identity'],
        'handoff_required_count': 1,
        'checked_at': datetime.now(UTC).isoformat(),
    }
    if drift:
        fresh['handoff_components'] = [dict(plan['handoff_components'][0], capsule_spec_sha256='b'*64), plan['handoff_components'][1]]
        fresh['handoff_fingerprint'] = handoff_fingerprint(fresh['handoff_components'])
    monkeypatch.setattr(acceptance, 'review_tenant_release_preflight_committed', lambda **_: fresh)
    monkeypatch.setattr(
        acceptance, 'verify_capsule_provider_admin_authority',
        lambda **_: {
            'scope_count': 2, 'scoped_resources': authority._capsule_admin_scope(plan['handoff_components']),
            'provider_username': 'kubernetes-admin',
            'provider_groups': ['system:authenticated'],
            'provider_credential_id': 'X509SHA256=test',
            'verification_source': 'kubernetes_self_subject_review',
            'authorization_source': 'kubernetes_self_subject_access_review',
        },
    )
    return plan, session


def test_capsule_acceptance_commits_consent_only_after_read_only_provider_proof(monkeypatch):
    plan, session = _bound_service(monkeypatch)
    accepted = acceptance.accept_capsule_successor_handoff_committed(
        tenant_id='tenant-1', actor_user_id=44,
        plan_sha256=plan['plan_sha256'], confirmed=True,
    )
    assert accepted['status'] == 'platform_admin_handoff_accepted'
    assert accepted['authority_mode'] == 'capsule_platform_admin_governed'
    assert accepted['consent_verified'] is True
    assert accepted['provider_handoff_verified'] is False
    assert accepted['provider_mutation_performed'] is False
    assert accepted['release_authorized'] is False
    assert accepted['secret_material_persisted'] is False
    assert len(session.events) == session.commits == 1
    assert session.events[0].action == 'tenant.release.capsule_platform_admin_handoff_accepted'


def test_capsule_acceptance_rejects_scope_drift_and_same_plan_replay(monkeypatch):
    plan, session = _bound_service(monkeypatch, drift=True)
    with pytest.raises(ValueError, match='scope changed'):
        acceptance.accept_capsule_successor_handoff_committed(
            tenant_id='tenant-1', actor_user_id=44,
            plan_sha256=plan['plan_sha256'], confirmed=True,
        )
    assert session.commits == 0
    plan, session = _bound_service(
        monkeypatch, previous={'plan_sha256': plan['plan_sha256']},
    )
    with pytest.raises(ValueError, match='already|superseded|changed'):
        acceptance.accept_capsule_successor_handoff_committed(
            tenant_id='tenant-1', actor_user_id=44,
            plan_sha256=plan['plan_sha256'], confirmed=True,
        )
    assert session.commits == 0


def test_capsule_release_step_3_uses_csrf_and_dedicated_read_model_without_enabling_transfer():
    from jinja2 import Environment

    root = Path(__file__).resolve().parents[3]
    source = (root / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text(
        encoding='utf-8'
    )
    Environment(autoescape=True).parse(source)
    fragment = source.split("if tenant.provider_key == 'capsule' %}", 1)[1].split(
        "if tenant.provider_key == 'native_kubernetes'", 1
    )[0]
    assert 'row.release_capsule_successor_acceptance' in fragment
    assert 'row.capsule_successor_acceptance_current' in fragment
    assert "accept_capsule_successor_handoff_route" in fragment
    assert 'confirm_capsule_successor_acceptance' in fragment
    assert 'name="csrf_token"' in fragment
    assert 'name="plan_sha256"' in fragment
    assert 'hx-target="#tenant-management-detail"' in fragment
    assert 'Verified Kubernetes TLS required' in fragment
    assert 'No Capsule mutation' in fragment
    route = (root / 'app/kubernetes/tenant/routes.py').read_text(encoding='utf-8')
    assert route.count("def accept_capsule_successor_handoff_route") == 1
    assert "@tenant_bp.post('/tenants/<string:tenant_id>/release-handoff/capsule-successor-accept')" in route
    assert 'accept_capsule_successor_handoff_committed(' in route
    read = (root / 'app/kubernetes/tenant/registry_context.py').read_text(encoding='utf-8')
    assert "('kubernetes_tenant_release_capsule_successor_acceptance', capsule_successor_acceptances)" in read
    assert "row['capsule_successor_acceptance_current'] = bool(" in read
