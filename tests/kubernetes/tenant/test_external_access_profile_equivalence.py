from __future__ import annotations

from copy import deepcopy

import pytest

from app.kubernetes.tenant.access import (
    ACCESS_PROFILE_CATALOG, capsule_cluster_role_manifest, get_access_profile,
)
from app.kubernetes.tenant.external_access_profile_equivalence import (
    _require_committed_capsule_binding,
    classify_external_role_profile,
)


def _provider_role(key='viewer', version=1):
    profile = get_access_profile(key, version)
    role = deepcopy(capsule_cluster_role_manifest(profile))
    role['metadata'].update({'uid': 'role-uid', 'resourceVersion': '7'})
    return role


@pytest.mark.parametrize('key,version', list(sorted(ACCESS_PROFILE_CATALOG)))
def test_only_exact_builtin_profile_is_equivalent_without_import_permission(key, version):
    result = classify_external_role_profile(_provider_role(key, version))
    assert result['equivalent_profile'] == key
    assert result['equivalent_version'] == version
    assert result['decision'] == 'principal_and_scope_review_required'
    assert result['import_authorized'] is False
    assert result['effective_rbac_verified'] is False
    assert result['identity_verified'] is False
    assert result['provider_mutation_performed'] is False
    assert len(result['permission_sha256']) == 64


def test_extra_privileges_cannot_be_mapped_as_less_privileged_profile():
    role = _provider_role('viewer')
    role['rules'][0]['verbs'].append('delete')
    result = classify_external_role_profile(role)
    assert result['equivalent_profile'] is None
    assert result['decision'] == 'no_exact_profile'


@pytest.mark.parametrize('mutation', [
    lambda role: role['rules'][0].update({'verbs': ['*']}),
    lambda role: role['rules'][0].update({'resources': ['*']}),
    lambda role: role['rules'][0].update({'apiGroups': ['*']}),
    lambda role: role['rules'][0].update({'resourceNames': ['named-only']}),
    lambda role: role['rules'][0].update({'nonResourceURLs': ['/metrics']}),
    lambda role: role.update({'aggregationRule': {'clusterRoleSelectors': []}}),
    lambda role: role['metadata'].update({'uid': ''}),
    lambda role: role['metadata'].update({'resourceVersion': ''}),
])
def test_unsupported_role_permissions_and_provider_identity_fail_closed(mutation):
    role = _provider_role()
    mutation(role)
    with pytest.raises(ValueError):
        classify_external_role_profile(role)


def test_role_equality_is_order_independent_but_remains_exact():
    role = _provider_role('operator')
    role['rules'].reverse()
    for rule in role['rules']:
        rule['verbs'].reverse()
        rule['resources'].reverse()
    result = classify_external_role_profile(role)
    assert result['equivalent_profile'] == 'operator'
    assert result['import_authorized'] is False


def test_capsule_profile_review_accepts_single_foreign_source_binding_only():
    from datetime import UTC, datetime

    tenant = type('TenantRef', (), {'id': 'tenant-a', 'cluster_id': 'cluster-a'})()
    observation = {
        'provider': 'capsule', 'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'observed_at': datetime.now(UTC).isoformat(),
        'bindings': [{
            'source': 'rules.permissions.bindings', 'ownership': 'external',
            'cluster_role_name': 'platform-reader',
            'subjects': [{'kind': 'Group', 'name': 'platform-team', 'namespace': ''}],
        }],
    }
    result = _require_committed_capsule_binding(
        observation, tenant=tenant, binding_index=0, now=datetime.now(UTC)
    )
    assert result['cluster_role_name'] == 'platform-reader'


@pytest.mark.parametrize('bad', [
    lambda rows: rows[0].update(ownership='kaori'),
    lambda rows: rows[0].update(cluster_role_name=''),
    lambda rows: rows[0].update(subjects=[]),
    lambda rows: rows.append(deepcopy(rows[0])),
])
def test_capsule_profile_review_fails_on_managed_or_ambiguous_binding(bad):
    from datetime import UTC, datetime

    tenant = type('TenantRef', (), {'id': 'tenant-a', 'cluster_id': 'cluster-a'})()
    rows = [{
        'source': 'additionalRoleBindings', 'ownership': 'external',
        'cluster_role_name': 'reader',
        'subjects': [{'kind': 'User', 'name': 'operator', 'namespace': ''}],
    }]
    bad(rows)
    observation = {
        'provider': 'capsule', 'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'observed_at': datetime.now(UTC).isoformat(), 'bindings': rows,
    }
    with pytest.raises(ValueError):
        _require_committed_capsule_binding(
            observation, tenant=tenant, binding_index=0, now=datetime.now(UTC)
        )
