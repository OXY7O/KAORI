from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.external_native_access_observation import normalize_native_role_binding


def _binding(
    *,
    subject_kind='User',
    subject_name='alice',
    subject_namespace=None,
    role_kind='ClusterRole',
    role_name='view',
    labels=None,
):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name='existing-binding',
            uid='role-binding-uid',
            resource_version='14',
            labels=labels or {},
        ),
        role_ref=SimpleNamespace(
            kind=role_kind, name=role_name, api_group='rbac.authorization.k8s.io'
        ),
        subjects=[SimpleNamespace(
            kind=subject_kind, name=subject_name, namespace=subject_namespace
        )],
    )


def test_native_foreign_rolebinding_stays_observed_and_keeps_exact_subject():
    result = normalize_native_role_binding(
        _binding(), namespace='sandbox', grant_ids={'grant-1'}
    )
    assert result['namespace'] == 'sandbox'
    assert result['role_ref'] == {'kind': 'ClusterRole', 'name': 'view'}
    assert result['subjects'] == [{'kind': 'User', 'name': 'alice', 'namespace': ''}]
    assert result['ownership'] == 'external_observed'
    assert result['kaori_grant_id'] is None
    assert result['uid'] == 'role-binding-uid'
    assert result['resource_version'] == '14'
    assert result['effective_permissions_verified'] is False


def test_native_labels_are_only_correlated_when_grant_belongs_to_tenant():
    labels = {
        'app.kubernetes.io/managed-by': 'kaori',
        'kaori.io/access-grant': 'grant-1',
    }
    obj = _binding(role_kind='Role', role_name='kaori-viewer', labels=labels)
    claimed = normalize_native_role_binding(
        obj, namespace='sandbox', grant_ids=set()
    )
    assert claimed['ownership'] == 'kaori_marker_unverified'
    assert claimed['claimed_grant_marker'] == 'grant-1'
    assert claimed['kaori_grant_id'] is None

    correlated = normalize_native_role_binding(
        obj, namespace='sandbox', grant_ids={'grant-1'}
    )
    assert correlated['ownership'] == 'kaori_correlated'
    assert correlated['kaori_grant_id'] == 'grant-1'
    assert correlated['effective_permissions_verified'] is False


def test_native_serviceaccount_subject_requires_namespace():
    with pytest.raises(ValueError, match='explicit namespace'):
        normalize_native_role_binding(
            _binding(subject_kind='ServiceAccount', subject_name='job'),
            namespace='sandbox',
            grant_ids=set(),
        )


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('subject_kind', 'Unrecognized'),
        ('subject_name', ''),
        ('role_kind', 'ClusterRoleBinding'),
        ('role_name', ''),
    ],
)
def test_native_unsupported_subject_or_role_reference_is_rejected(field, value):
    with pytest.raises(ValueError):
        normalize_native_role_binding(
            _binding(**{field: value}), namespace='sandbox', grant_ids=set()
        )


def test_native_serviceaccount_identity_is_preserved_but_not_imported():
    observed = normalize_native_role_binding(
        _binding(
            subject_kind='ServiceAccount',
            subject_name='pipeline',
            subject_namespace='jobs',
        ),
        namespace='sandbox',
        grant_ids=set(),
    )
    assert observed['subjects'] == [
        {'kind': 'ServiceAccount', 'name': 'pipeline', 'namespace': 'jobs'}
    ]
    assert observed['ownership'] == 'external_observed'
