from __future__ import annotations

from types import SimpleNamespace

from app.kubernetes.tenant.release_preflight import _release_blockers


def _tenant(**changes):
    values = {
        'ownership_status': 'adopted',
        'lifecycle_status': 'ready',
        'provider_key': 'native_kubernetes',
        'provider_state': 'native',
        'reconciliation_authority': 'native_kubernetes',
        'provider_evidence_json': {'provider_mutation_performed': False},
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _namespace(**changes):
    values = {
        'namespace': 'sandbox',
        'ownership_status': 'adopted',
        'provisioning_status': 'ready',
        'resource_profile_id': None,
        'provisioning_evidence_json': {'provider_mutation_performed': False},
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_release_preflight_rejects_destructive_or_foreign_ownership_and_live_dependencies():
    cases = [
        (_tenant(ownership_status='managed'), [_namespace()], {}),
        (_tenant(lifecycle_status='decommissioning'), [_namespace()], {}),
        (_tenant(provider_state='capsule_degraded'), [_namespace()], {}),
        (_tenant(reconciliation_authority='capsule'), [_namespace()], {}),
        (_tenant(), [_namespace(ownership_status='managed')], {}),
        (_tenant(), [_namespace(resource_profile_id=1)], {}),
        (_tenant(), [_namespace(provisioning_evidence_json={'provider_mutation_performed': True})], {}),
        (_tenant(), [_namespace(provisioning_evidence_json={})], {}),
        (_tenant(), [_namespace()], {'Access Grants': 2, 'credentials': 1}),
    ]
    for tenant, namespaces, counts in cases:
        assert _release_blockers(tenant, namespaces, counts=counts)


def test_external_adoption_without_active_dependencies_is_preflight_review_candidate_only():
    assert _release_blockers(
        _tenant(), [_namespace()], counts={
            'Access Grants': 0,
            'credentials': 0,
            'Memberships': 0,
        }
    ) == []
