from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_namespace_attachment_authority import (
    validate_capsule_namespace_attachment,
)


def _tenant(**overrides):
    base = {
        'cluster_id': 'cluster-a', 'provider_key': 'capsule',
        'provider_state': 'capsule', 'reconciliation_authority': 'capsule',
        'lifecycle_status': 'ready', 'ownership_status': 'adopted',
        'provider_reference': 'team-a',
        'provider_evidence_json': {'provider_uid': 'capsule-uid'},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _namespace(*, labels=None, owners=None, uid='ns-uid'):
    return SimpleNamespace(metadata=SimpleNamespace(
        name='team-a-dev', uid=uid, resource_version='42',
        labels=labels if labels is not None else {'capsule.clastix.io/tenant': 'team-a'},
        owner_references=owners or [],
        deletion_timestamp=None,
    ))


def _validate(tenant=None, namespace=None, status=None):
    return validate_capsule_namespace_attachment(
        tenant=tenant or _tenant(),
        cluster_id='cluster-a',
        capsule_item={
            'metadata': {
                'name': 'team-a', 'uid': 'capsule-uid', 'resourceVersion': '14',
            },
        },
        namespace=namespace or _namespace(),
        expected_namespace_uid='ns-uid',
        status_namespace_names=status if status is not None else set(),
    )


def test_matching_capsule_namespace_correlation_preserves_existing_provider_authority():
    evidence = _validate()
    assert evidence['namespace'] == 'team-a-dev'
    assert evidence['namespace_uid'] == 'ns-uid'
    assert evidence['capsule_tenant_uid'] == 'capsule-uid'
    assert evidence['authority'] == 'capsule'
    assert evidence['provider_mutation_performed'] is False


@pytest.mark.parametrize('override', [
    {'cluster_id': 'foreign'},
    {'provider_key': 'native_kubernetes'},
    {'provider_state': 'native'},
    {'reconciliation_authority': 'native_kubernetes'},
    {'lifecycle_status': 'released'},
    {'provider_reference': 'team-b'},
    {'provider_evidence_json': {'provider_uid': 'recreated'}},
])
def test_cross_cluster_wrong_authority_or_released_tenant_cannot_attach(override):
    with pytest.raises(ValueError):
        _validate(tenant=_tenant(**override))


def test_capsule_namespace_uid_replacement_is_rejected():
    with pytest.raises(ValueError, match='UID/resourceVersion'):
        _validate(namespace=_namespace(uid='recreated-namespace'))


def test_namespace_with_foreign_capsule_label_is_rejected_even_when_status_claims_it():
    with pytest.raises(ValueError, match='another Tenant'):
        _validate(
            namespace=_namespace(labels={'capsule.clastix.io/tenant': 'team-b'}),
            status={'team-a-dev'},
        )


def test_unlinked_namespace_is_not_claimed_by_capsule_just_because_it_is_in_cluster():
    with pytest.raises(ValueError, match='no authoritative'):
        _validate(namespace=_namespace(labels={}))


def test_capsule_status_membership_can_prove_link_if_no_label_present():
    evidence = _validate(namespace=_namespace(labels={}), status={'team-a-dev'})
    assert evidence['capsule_tenant_name'] == 'team-a'


def test_capsule_owner_reference_must_not_contradict_capsule_label():
    foreign = SimpleNamespace(kind='Tenant', name='team-b', api_version='capsule.clastix.io/v1beta2')
    with pytest.raises(ValueError, match='another Tenant'):
        _validate(namespace=_namespace(owners=[foreign]))


def test_multiple_capsule_claims_fail_closed():
    labels = {
        'capsule.clastix.io/tenant': 'team-a',
        'projectcapsule.dev/tenant': 'team-b',
    }
    with pytest.raises(ValueError, match='ambiguous'):
        _validate(namespace=_namespace(labels=labels))
