"""Capsule Released -> Discovery -> new-generation Re-Adopt UID/RV wiring.

Regression fixtures authored for #1231; tests are NOT executed under
the currently active CI/CD, runtime and Kubernetes provider HOLD.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.kubernetes.tenant import discovery_adoption as adoption


def _capsule_context():
    return SimpleNamespace(
        cluster=SimpleNamespace(id='cluster-a'),
        client=SimpleNamespace(),
        resource_name='capsule-demo',
        expected_provider_uid='capsule-uid',
        expected_provider_resource_version='57',
        tenant=SimpleNamespace(slug='capsule-demo'),
        environment_name='development',
        now=datetime.now(UTC),
    )


def _stub_capsule_discovery(monkeypatch):
    monkeypatch.setattr(
        adoption,
        '_read_capsule_tenant',
        lambda *_: (
            'v1beta2',
            {
                'metadata': {
                    'name': 'capsule-demo',
                    'uid': 'capsule-uid',
                    'resourceVersion': '57',
                    'labels': {},
                }
            },
        ),
    )
    monkeypatch.setattr(adoption, '_capsule_phase', lambda *_: 'Ready')
    monkeypatch.setattr(adoption, '_managed_capsule_map', lambda *_: {})
    monkeypatch.setattr(adoption, '_managed_namespace_map', lambda *_: {})
    monkeypatch.setattr(
        adoption,
        'observe_capsule_tenant_allocation',
        lambda *_args, **_kw: {
            'control_state': 'observed',
            'correlated_namespaces': [],
        },
    )
    monkeypatch.setattr(adoption, 'qualify_capsule_tenant_adoption', lambda **_kw: ('capsule', {}))
    monkeypatch.setattr(adoption, '_apply_capsule_allocation_capability_state', lambda *_a, **_kw: None)


def test_capsule_re_adopt_passes_live_tenant_rv_to_historical_handback_before_db_insert(monkeypatch):
    _stub_capsule_discovery(monkeypatch)
    seen = []
    writes = Mock()
    monkeypatch.setattr(adoption, 'db', SimpleNamespace(session=writes))

    def stale_handback(_tenant, *, provider_uid, resource_version):
        seen.append((provider_uid, resource_version))
        raise ValueError('Released Capsule handback RV differs from provider.')

    monkeypatch.setattr(adoption, '_released_predecessor_evidence', stale_handback)
    with pytest.raises(ValueError, match='handback RV differs'):
        adoption._adopt_capsule(_capsule_context())
    assert seen == [('capsule-uid', '57')]
    writes.add.assert_not_called()
    writes.flush.assert_not_called()


def test_capsule_re_adopt_records_prior_lineage_only_after_current_tenant_uid_rv(monkeypatch):
    _stub_capsule_discovery(monkeypatch)
    records = []
    session = SimpleNamespace(
        add=lambda value: records.append(value),
        flush=lambda: None,
    )
    monkeypatch.setattr(adoption, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(adoption, 'TenantEnvironment', lambda: SimpleNamespace())
    monkeypatch.setattr(adoption, '_capsule_namespace_records', lambda *_: [])
    monkeypatch.setattr(adoption, '_mirror_capsule_namespace_policies', lambda *_: None)
    monkeypatch.setattr(adoption, '_finalize_capsule_takeover', lambda *_: None)
    expected = {
        'predecessor_tenant_id': 'released-tenant-id',
        'predecessor_generation': 1,
        'provider_uid_verified': True,
    }
    calls = []

    def verified_predecessor(_tenant, *, provider_uid, resource_version):
        calls.append((provider_uid, resource_version))
        if (provider_uid, resource_version) != ('capsule-uid', '57'):
            raise ValueError('Refuse stale or replaced Capsule provider resource.')
        return expected

    monkeypatch.setattr(adoption, '_released_predecessor_evidence', verified_predecessor)
    context = _capsule_context()
    environment, namespace = adoption._adopt_capsule(context)
    assert calls == [('capsule-uid', '57')]
    assert context.tenant.provider_evidence_json['re_adoption_lineage'] == expected
    assert context.tenant.provider_evidence_json['resource_version'] == '57'
    assert context.tenant.provider_evidence_json['provider_mutation_performed'] is False
    assert environment in records
    assert namespace is None


def _capsule_allocation():
    return {
        'control_state': 'observed',
        'allocation_authority': 'capsule_tenant_resource_quotas',
        'correlated_namespaces': [
            {
                'name': 'demo-dev',
                'uid': 'ns-uid-1',
                'resource_version': '41',
                'allocation': {'quota': {'requests.cpu': '1'}},
            },
            {
                'name': 'demo-uat',
                'uid': 'ns-uid-2',
                'resource_version': '72',
                'allocation': {'quota': {'requests.memory': '1Gi'}},
            },
        ],
    }


def test_capsule_all_namespace_handbacks_are_verified_with_individual_rv_before_records(monkeypatch):
    context = _capsule_context()
    observed = []
    created = []
    writes = Mock()

    def verify(*, cluster_id, namespace, provider_uid, tenant_slug, resource_version):
        observed.append((cluster_id, namespace, provider_uid, tenant_slug, resource_version))
        if namespace == 'demo-uat':
            raise ValueError('Released Namespace has stale handback resourceVersion.')

    monkeypatch.setattr(adoption, '_verify_released_namespace_lineage', verify)
    monkeypatch.setattr(adoption, 'TenantNamespace', lambda: created.append('created'))
    monkeypatch.setattr(adoption, 'db', SimpleNamespace(session=writes))
    with pytest.raises(ValueError, match='stale handback'):
        adoption._capsule_namespace_records(
            context,
            SimpleNamespace(),
            _capsule_allocation(),
        )
    assert observed == [
        ('cluster-a', 'demo-dev', 'ns-uid-1', 'capsule-demo', '41'),
        ('cluster-a', 'demo-uat', 'ns-uid-2', 'capsule-demo', '72'),
    ]
    assert created == []
    writes.add.assert_not_called()
    writes.flush.assert_not_called()


def test_capsule_namespace_re_adopt_uses_each_verified_uid_rv_for_new_generation(monkeypatch):
    context = _capsule_context()
    checks = []
    records = []
    session = SimpleNamespace(add=lambda obj: records.append(obj))

    def verify(**kwargs):
        checks.append((kwargs['namespace'], kwargs['provider_uid'], kwargs['resource_version']))

    monkeypatch.setattr(adoption, '_verify_released_namespace_lineage', verify)
    monkeypatch.setattr(adoption, 'TenantNamespace', lambda: SimpleNamespace())
    monkeypatch.setattr(adoption, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(adoption, '_next_namespace_generation', lambda **_kw: 8)
    rows = adoption._capsule_namespace_records(
        context,
        SimpleNamespace(),
        _capsule_allocation(),
    )
    assert checks == [('demo-dev', 'ns-uid-1', '41'), ('demo-uat', 'ns-uid-2', '72')]
    assert len(rows) == len(records) == 2
    assert [row.provider_reference for row in rows] == ['ns-uid-1', 'ns-uid-2']
    assert [row.generation for row in rows] == [8, 8]
    assert [row.provisioning_evidence_json['resource_version'] for row in rows] == ['41', '72']
    assert all(row.provisioning_evidence_json['provider_mutation_performed'] is False for row in rows)


@pytest.mark.parametrize(
    ('previous_rv', 'observed_rv'),
    [
        ('41', '42'),
        ('41', None),
        (None, '41'),
    ],
)
def test_managed_released_handoff_stays_fail_closed_for_stale_or_missing_rv(
    previous_rv,
    observed_rv,
):
    provider = {
        'provider_mutation_performed': True,
        'handback_governance': {
            'status': 'verified',
            'release_plan_sha256': 'plan-sha',
            'successor_owner': 'successor',
            'provider_uid': 'ns-uid-1',
            'resource_version': previous_rv,
        },
    }
    release = {
        'status': 'released',
        'plan_sha256': 'plan-sha',
        'successor_owner': 'successor',
        'release_mode': 'managed_handoff',
    }
    with pytest.raises(ValueError):
        adoption._require_re_adoption_handback_for_managed_release(
            provider_evidence=provider,
            release_evidence=release,
            provider_uid='ns-uid-1',
            resource_version=observed_rv,
        )


def test_matching_verified_managed_handback_is_reviewable_but_not_automatic_readopt():
    provider = {
        'provider_mutation_performed': True,
        'handback_governance': {
            'status': 'verified',
            'release_plan_sha256': 'plan-sha',
            'successor_owner': 'successor',
            'provider_uid': 'ns-uid-1',
            'resource_version': '41',
        },
    }
    release = {
        'status': 'released',
        'plan_sha256': 'plan-sha',
        'successor_owner': 'successor',
        'release_mode': 'managed_handoff',
    }
    assert (
        adoption._require_re_adoption_handback_for_managed_release(
            provider_evidence=provider,
            release_evidence=release,
            provider_uid='ns-uid-1',
            resource_version='41',
        )
        is None
    )


@pytest.mark.parametrize(
    ('provider_key', 'reference', 'namespace_versions'),
    [
        ('capsule', 'capsule-demo', {'demo-dev': 'unrelated-ns-rv'}),
        ('native_kubernetes', 'demo-dev', {'demo-dev': '57'}),
    ],
)
def test_released_predecessor_selects_own_provider_handback_resource_version(
    monkeypatch,
    provider_key,
    reference,
    namespace_versions,
):
    """Capsule cluster-scoped Tenant CR must not resolve its RV from a Namespace map."""
    prior = SimpleNamespace(
        id='old-tenant',
        generation=3,
        correlation_id='prior-correlation',
        provider_key=provider_key,
        provider_evidence_json={
            'provider_uid': 'old-uid',
            'provider_mutation_performed': True,
            'release_governance': {
                'status': 'released',
                'release_mode': 'managed_handoff',
                'tenant_id': 'old-tenant',
                'plan_sha256': 'prior-plan',
                'successor_owner': 'platform-team',
                'released_at': '2026-10-11T00:00:00+00:00',
            },
            'handback_governance': {
                'status': 'verified',
                'provider_uid': 'old-uid',
                'release_plan_sha256': 'prior-plan',
                'successor_owner': 'platform-team',
                'resource_version': '57' if provider_key == 'capsule' else 'stale-tenant-field',
                'provider_resource_versions': namespace_versions,
            },
        },
    )

    class _Query:
        def filter_by(self, **_kwargs):
            return self

        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return prior

    model = SimpleNamespace(
        query=_Query(),
        lifecycle_status='released',
        generation=SimpleNamespace(desc=lambda: 'newest-first'),
    )
    monkeypatch.setattr(adoption, 'Tenant', model)
    current = SimpleNamespace(
        cluster_id='cluster-1',
        slug='demo',
        provider_key=provider_key,
        provider_reference=reference,
    )
    lineage = adoption._released_predecessor_evidence(
        current,
        provider_uid='old-uid',
        resource_version='57',
    )
    assert lineage['predecessor_tenant_id'] == 'old-tenant'
    assert lineage['predecessor_generation'] == 3
    assert lineage['provider_uid_verified'] is True
