from __future__ import annotations

from copy import deepcopy

import pytest

from app.kubernetes.tenant.discovery_service import select_capsule_namespace_attachment_candidate


def _allocation(*, label_claims=None, owner_claims=None):
    row = {
        'name': 'team-app',
        'uid': 'ns-uid-101',
        'resource_version': '42',
        'label_claims': ['blue-tenant'] if label_claims is None else label_claims,
        'owner_claims': [] if owner_claims is None else owner_claims,
        'allocation': {
            'control_state': 'observed',
            'quota': {'requests.cpu': '2'},
            'limits': {},
            'storage_policy': {},
            'effective_hash': 'stable-allocation-hash',
            'unsupported_dimensions': [],
            'ambiguous_dimensions': [],
        },
    }
    return {
        'correlated_namespaces': [row],
        'allocation_authority': 'capsule_tenant_resource_quotas',
        'authority_unsupported_dimensions': [],
        'authority_ambiguous_dimensions': [],
        'ambiguous_dimensions': [],
    }


def _select(allocation, **kwargs):
    return select_capsule_namespace_attachment_candidate(
        allocation, namespace='team-app', capsule_tenant_name='blue-tenant', **kwargs,
    )


def test_capsule_namespace_attachment_matches_exact_uid_rv_and_authority_without_mutation():
    payload = _allocation()
    copy = deepcopy(payload)
    selected = _select(
        payload, expected_uid='ns-uid-101', expected_resource_version='42',
    )
    assert selected['uid'] == 'ns-uid-101'
    assert selected['resource_version'] == '42'
    assert selected['allocation']['quota'] == {'requests.cpu': '2'}
    assert payload == copy


@pytest.mark.parametrize('claims', [
    [],
    ['foreign-tenant'],
    ['blue-tenant', 'foreign-tenant'],
])
def test_status_only_or_conflicting_capsule_label_cannot_claim_namespace(claims):
    with pytest.raises(ValueError, match='unambiguous Tenant'):
        _select(_allocation(label_claims=claims))


def test_exact_capsule_owner_reference_is_valid_when_label_is_absent():
    observed = _select(_allocation(label_claims=[], owner_claims=['blue-tenant']))
    assert observed['name'] == 'team-app'


def test_capsule_owner_ref_disagrees_with_label_fails_closed():
    with pytest.raises(ValueError, match='unambiguous Tenant'):
        _select(_allocation(owner_claims=['foreign-tenant']))


@pytest.mark.parametrize('expected_uid,expected_rv', [
    ('replaced-uid', '42'),
    ('ns-uid-101', '43'),
])
def test_capsule_namespace_attachment_rejects_stale_preflight(expected_uid, expected_rv):
    with pytest.raises(ValueError, match='changed'):
        _select(
            _allocation(), expected_uid=expected_uid,
            expected_resource_version=expected_rv,
        )


def test_capsule_namespace_already_missing_or_multiple_provider_correlations():
    missing = _allocation()
    missing['correlated_namespaces'] = []
    with pytest.raises(ValueError, match='uniquely correlated'):
        _select(missing)
    duplicated = _allocation()
    duplicated['correlated_namespaces'].append(
        deepcopy(duplicated['correlated_namespaces'][0])
    )
    with pytest.raises(ValueError, match='uniquely correlated'):
        _select(duplicated)


@pytest.mark.parametrize('field,value', [
    ('authority_unsupported_dimensions', ['unsupported API']),
    ('authority_ambiguous_dimensions', ['mixed authority']),
    ('ambiguous_dimensions', ['external ownership ambiguity']),
])
def test_capsule_attachment_rejects_unsupported_or_ambiguous_authority(field, value):
    payload = _allocation()
    payload[field] = value
    with pytest.raises(ValueError, match='authority or Namespace correlation'):
        _select(payload)


def test_capsule_attachment_refuses_provider_unavailable_or_unsupported_allocation():
    payload = _allocation()
    payload['correlated_namespaces'][0]['allocation']['control_state'] = 'control_unavailable'
    with pytest.raises(ValueError, match='allocation'):
        _select(payload)

    payload = _allocation()
    payload['correlated_namespaces'][0]['uid'] = ''
    with pytest.raises(ValueError, match='identity evidence'):
        _select(payload)
