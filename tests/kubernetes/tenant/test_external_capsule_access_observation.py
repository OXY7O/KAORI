from __future__ import annotations

import pytest

from app.kubernetes.tenant.external_access_observation import normalize_capsule_access_spec


def test_capsule_owners_and_foreign_bindings_stay_observed_not_auto_adopted() -> None:
    result = normalize_capsule_access_spec({
        'owners': [{'kind': 'User', 'name': 'external-admin'}],
        'additionalRoleBindings': [{
            'clusterRoleName': 'view',
            'subjects': [{'kind': 'Group', 'name': 'engineering'}],
        }],
        'rules': [{
            'namespaceSelector': {'matchLabels': {'env': 'production'}},
            'permissions': {'bindings': [{
                'clusterRoleName': 'edit',
                'subjects': [{'kind': 'User', 'name': 'external-dev'}],
            }]},
        }],
    })
    assert result['owner_count'] == 1
    assert result['external_count'] == 2
    assert result['kaori_count'] == 0
    assert result['status'] == 'review_required'
    assert all(binding['governance'] == 'observed_review_required' for binding in result['bindings'])
    assert result['bindings'][1]['scope_selector'] == {'matchLabels': {'env': 'production'}}


def test_kaori_grant_marker_requires_both_manager_and_grant_id() -> None:
    result = normalize_capsule_access_spec({
        'additionalRoleBindings': [
            {
                'clusterRoleName': 'kaori-tenant-viewer-v1',
                'labels': {
                    'app.kubernetes.io/managed-by': 'kaori',
                    'kaori.io/access-grant': 'grant-123',
                },
                'subjects': [{'kind': 'User', 'name': 'super'}],
            },
            {
                'clusterRoleName': 'kaori-tenant-viewer-v1',
                'labels': {'app.kubernetes.io/managed-by': 'kaori'},
                'subjects': [{'kind': 'User', 'name': 'not-imported'}],
            },
        ],
    })
    assert result['kaori_count'] == 1
    assert result['external_count'] == 1
    assert result['bindings'][0]['kaori_grant_id'] == 'grant-123'
    assert result['bindings'][1]['kaori_grant_id'] is None


@pytest.mark.parametrize(
    'spec',
    [
        {'owners': {'kind': 'User', 'name': 'bad'}},
        {'rules': [{'permissions': {'bindings': {}}}]},
        {'additionalRoleBindings': [{'subjects': 'not-list'}]},
        {'rules': [{'namespaceSelector': 'invalid', 'permissions': {'bindings': [{}]}}]},
        {'additionalRoleBindings': [None]},
    ],
)
def test_external_access_malformed_provider_evidence_fails_closed(spec) -> None:
    with pytest.raises(ValueError):
        normalize_capsule_access_spec(spec)


def test_external_access_inventory_bounded_to_prevent_unlimited_provider_payload() -> None:
    with pytest.raises(ValueError, match='bounded'):
        normalize_capsule_access_spec({'additionalRoleBindings': [{}] * 201})
