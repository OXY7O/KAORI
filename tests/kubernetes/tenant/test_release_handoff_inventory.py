from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.release_handoff_inventory import (
    capsule_tenant_handoff_evidence,
    capsule_namespace_handoff_evidence,
    handoff_fingerprint,
    native_namespace_handoff_evidence,
)


def _namespace(*, manager: str = 'kaori', tenant_id: str = 'tenant-a'):
    return SimpleNamespace(metadata=SimpleNamespace(
        name='sandbox', uid='ns-uid', resource_version='12',
        labels={
            'app.kubernetes.io/managed-by': manager,
            'kaori.io/tenant-id': tenant_id,
        },
    ))


def _record(*, profile_id: int | None = 2, effective_hash: str = 'known'):
    return SimpleNamespace(
        namespace='sandbox',
        resource_profile_id=profile_id,
        effective_hash=effective_hash,
        provisioning_evidence_json={
            'allocation_control_state': 'kaori_managed' if profile_id else 'observed',
            'provider_mutation_performed': bool(profile_id),
        },
    )


def _allocation(*, sources=None, effective_hash: str = 'known'):
    return {
        'control_state': 'observed',
        'effective_hash': effective_hash,
        'source_resources': sources if sources is not None else [{
            'kind': 'ResourceQuota',
            'name': 'namespace-quota',
            'uid': 'quota-uid',
            'resource_version': '40',
            'managed_by': 'kaori',
            'tenant_id': 'tenant-a',
        }],
    }


def test_native_managed_quota_and_namespace_require_explicit_external_handoff():
    items, blockers = native_namespace_handoff_evidence(
        record=_record(), namespace=_namespace(),
        observation=_allocation(), tenant_id='tenant-a',
    )
    assert [(item['kind'], item['name']) for item in items] == [
        ('Namespace', 'sandbox'),
        ('ResourceQuota', 'namespace-quota'),
    ]
    assert all(item['ownership'] == 'kaori_marker_correlated' for item in items)
    assert all(item['handoff'] == 'external_acceptance_required' for item in items)
    assert items[1]['uid'] == 'quota-uid'
    assert items[1]['resource_version'] == '40'
    assert any('external handoff' in reason for reason in blockers)


def test_native_observation_only_unlabelled_resources_have_no_handoff_blockers():
    namespace = SimpleNamespace(metadata=SimpleNamespace(
        name='sandbox', uid='uid', resource_version='8', labels={}
    ))
    items, blockers = native_namespace_handoff_evidence(
        record=_record(profile_id=None), namespace=namespace,
        observation=_allocation(sources=[]), tenant_id='tenant-a',
    )
    assert len(items) == 1
    assert items[0]['handoff'] == 'observe_only'
    assert blockers == []


def test_native_conflicting_marker_and_allocation_hash_fail_closed():
    items, blockers = native_namespace_handoff_evidence(
        record=_record(), namespace=_namespace(tenant_id='other-tenant'),
        observation=_allocation(effective_hash='drifted'), tenant_id='tenant-a',
    )
    assert items[0]['ownership'] == 'marker_conflict'
    assert any('ownership markers' in reason for reason in blockers)
    assert any('allocation hash changed' in reason for reason in blockers)


@pytest.mark.parametrize('source', [
    {'kind': 'ClusterRole', 'name': 'unknown', 'uid': 'uid', 'resource_version': '1'},
    {'kind': 'LimitRange', 'name': 'limits', 'uid': '', 'resource_version': '1'},
])
def test_native_rejects_unsupported_or_unidentified_provider_components(source):
    with pytest.raises(ValueError):
        native_namespace_handoff_evidence(
            record=_record(), namespace=_namespace(),
            observation=_allocation(sources=[source]), tenant_id='tenant-a',
        )


def test_capsule_authority_remains_observed_without_mutation():
    tenant = SimpleNamespace(
        id='tenant-a',
        provider_evidence_json={'provider_mutation_performed': False},
    )
    components, blockers = capsule_tenant_handoff_evidence(
        tenant=tenant,
        tenant_item={
            'metadata': {
                'name': 'sandbox', 'uid': 'capsule-uid',
                'resourceVersion': '36', 'labels': {},
            },
            'spec': {'resourceQuotas': {'scope': 'Tenant', 'items': []}},
        },
    )
    assert blockers == []
    assert components[0]['authority'] == 'capsule'
    assert components[0]['uid'] == 'capsule-uid'
    assert components[0]['resource_quotas_present'] == 'true'
    assert components[0]['handoff'] == 'observe_only'


def test_capsule_modified_allocation_cannot_silently_release():
    tenant = SimpleNamespace(
        id='tenant-a',
        provider_evidence_json={'provider_mutation_performed': True},
    )
    components, blockers = capsule_tenant_handoff_evidence(
        tenant=tenant,
        tenant_item={
            'metadata': {'name': 'sandbox', 'uid': 'uid', 'resourceVersion': '1'},
            'spec': {},
        },
    )
    assert any('explicit provider authority handoff' in reason for reason in blockers)
    assert components[0]['handoff'] == 'external_acceptance_required'
    assert components[0]['ownership'] == 'external_or_unattributed'


def test_fingerprint_is_order_independent_but_detects_changed_provider_versions():
    objects = [
        {'namespace': 'a', 'kind': 'Namespace', 'name': 'a', 'uid': 'id-a', 'resource_version': '1'},
        {'namespace': 'a', 'kind': 'ResourceQuota', 'name': 'q', 'uid': 'id-q', 'resource_version': '2'},
    ]
    assert handoff_fingerprint(objects) == handoff_fingerprint(list(reversed(objects)))
    changed = [dict(item) for item in objects]
    changed[1]['resource_version'] = '3'
    assert handoff_fingerprint(objects) != handoff_fingerprint(changed)


def test_capsule_namespace_requires_proven_tenant_claim_and_immutable_uid():
    record = SimpleNamespace(namespace='sandbox', provider_reference='ns-uid')
    linked = SimpleNamespace(metadata=SimpleNamespace(
        name='sandbox', uid='ns-uid', resource_version='14',
        labels={'projectcapsule.dev/tenant': 'tenant-capsule'},
    ))
    component, blockers = capsule_namespace_handoff_evidence(
        record=record, namespace=linked,
        tenant_name='tenant-capsule', tenant_id='kaori-id',
        status_namespace_names=set(),
    )
    assert blockers == []
    assert component['authority'] == 'capsule'
    assert component['uid'] == 'ns-uid'
    assert component['resource_version'] == '14'

    foreign = SimpleNamespace(metadata=SimpleNamespace(
        name='sandbox', uid='ns-uid', resource_version='14',
        labels={'projectcapsule.dev/tenant': 'other-capsule'},
    ))
    _, blockers = capsule_namespace_handoff_evidence(
        record=record, namespace=foreign,
        tenant_name='tenant-capsule', tenant_id='kaori-id',
        status_namespace_names={'sandbox'},
    )
    assert any('no verifiable Tenant ownership' in reason for reason in blockers)

    replaced = SimpleNamespace(metadata=SimpleNamespace(
        name='sandbox', uid='new-uid', resource_version='15',
        labels={'projectcapsule.dev/tenant': 'tenant-capsule'},
    ))
    with pytest.raises(ValueError, match='name/UID differs'):
        capsule_namespace_handoff_evidence(
            record=record, namespace=replaced,
            tenant_name='tenant-capsule', tenant_id='kaori-id',
            status_namespace_names=set(),
        )


def test_capsule_spec_fingerprint_is_canonical_and_binds_all_provider_controls():
    """#1227: provider quota, limits, owner and RBAC changes invalidate handoff."""
    from copy import deepcopy

    tenant = SimpleNamespace(
        id='tenant-a', provider_evidence_json={'provider_mutation_performed': True},
    )
    spec = {
        'resourceQuotas': {'scope': 'Tenant', 'items': [{'hard': {'pods': '10'}}]},
        'limitRanges': {'items': [{'limits': [{'type': 'Container'}]}]},
        'namespaceOptions': {'quota': 2},
        'owners': [{'kind': 'User', 'name': 'platform-team'}],
        'rules': [{'permissions': {'bindings': [{'clusterRoleName': 'viewer'}]}}],
        'additionalRoleBindings': [],
    }

    def observe(value, version='1'):
        components, blockers = capsule_tenant_handoff_evidence(
            tenant=tenant,
            tenant_item={
                'metadata': {'name': 'sandbox', 'uid': 'capsule-uid', 'resourceVersion': version},
                'spec': value,
            },
        )
        assert len(components) == 1
        assert components[0]['handoff'] == 'external_acceptance_required'
        assert any('explicit provider authority handoff' in reason for reason in blockers)
        assert len(components[0]['capsule_spec_sha256']) == 64
        assert 'owners' not in components[0]
        assert 'rules' not in components[0]
        return handoff_fingerprint(components), components[0]['capsule_spec_sha256']

    baseline_fingerprint, baseline_digest = observe(spec)
    reordered = dict(reversed(list(spec.items())))
    assert observe(reordered) == (baseline_fingerprint, baseline_digest)

    changes = [
        ('resourceQuotas', {'scope': 'Tenant', 'items': [{'hard': {'pods': '20'}}]}),
        ('limitRanges', {'items': []}),
        ('namespaceOptions', {'quota': 3}),
        ('owners', [{'kind': 'User', 'name': 'different-successor'}]),
        ('rules', []),
        ('additionalRoleBindings', [{'clusterRoleName': 'admin'}]),
    ]
    for field, replacement in changes:
        changed = deepcopy(spec)
        changed[field] = replacement
        fingerprint, digest = observe(changed)  # Same UID/RV as initial preflight.
        assert fingerprint != baseline_fingerprint
        assert digest != baseline_digest


@pytest.mark.parametrize('bad_spec', [
    None,
    [],
    'unexpected',
    {'owners': {}},
    {'resourceQuotas': []},
    {'rules': {}},
    {'namespaceOptions': []},
    {'bad': {1, 2}},
    {'bad': float('nan')},
    {'owners': 'a' * 262145},
])
def test_capsule_release_inventory_rejects_unbounded_or_unsupported_spec(bad_spec):
    tenant = SimpleNamespace(
        id='tenant-a', provider_evidence_json={'provider_mutation_performed': False},
    )
    with pytest.raises(ValueError, match='Capsule Tenant'):
        capsule_tenant_handoff_evidence(
            tenant=tenant,
            tenant_item={
                'metadata': {'name': 'sandbox', 'uid': 'capsule-uid', 'resourceVersion': '7'},
                'spec': bad_spec,
            },
        )


def test_capsule_release_scope_digest_is_read_only_and_visible_as_technical_evidence():
    from pathlib import Path
    from jinja2 import Environment

    root = Path(__file__).resolve().parents[3]
    partial = (root / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text(
        encoding='utf-8'
    )
    Environment(autoescape=True).parse(partial)
    inventory = partial.split('id="tenant-release-stage-inventory"', 1)[1].split('</section>', 1)[0]
    assert "item.kind == 'CapsuleTenant' and item.get('capsule_spec_sha256')" in inventory
    assert 'Observed Capsule spec SHA-256' in inventory
    assert '{{ item.capsule_spec_sha256 }}' in inventory
    assert 'Read-only scope evidence' in inventory
    assert 'Provider UID' in inventory
    assert 'Resource Version' in inventory
