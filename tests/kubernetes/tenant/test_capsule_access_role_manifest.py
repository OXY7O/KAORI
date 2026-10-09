from __future__ import annotations

import yaml
import pytest

from app.kubernetes.tenant.access import (
    ACCESS_PROFILE_CATALOG,
    capsule_cluster_role_manifest,
    capsule_cluster_role_name,
    get_access_profile,
)


@pytest.mark.parametrize(
    ('key', 'expected_name'),
    [
        ('viewer', 'kaori-tenant-viewer-v1'),
        ('operator', 'kaori-tenant-operator-v1'),
        ('tenant_admin', 'kaori-tenant-tenant-admin-v1'),
        ('deployer', 'kaori-tenant-deployer-v1'),
    ],
)
def test_capsule_clusterrole_manifest_matches_code_owned_profile_exactly(key: str, expected_name: str) -> None:
    profile = get_access_profile(key, 1)
    document = capsule_cluster_role_manifest(profile)

    assert capsule_cluster_role_name(profile) == expected_name
    assert document['kind'] == 'ClusterRole'
    assert document['apiVersion'] == 'rbac.authorization.k8s.io/v1'
    assert document['metadata'] == {'name': expected_name}
    assert document['rules'] == [
        {
            'apiGroups': list(rule.api_groups),
            'resources': list(rule.resources),
            'verbs': list(rule.verbs),
        }
        for rule in profile.rules
    ]
    assert all('*' not in rule['verbs'] for rule in document['rules'])
    assert 'aggregationRule' not in document
    assert 'subjects' not in document
    assert 'ClusterRoleBinding' not in yaml.safe_dump(document)


def test_capsule_four_role_bundle_is_valid_individually_loadable_yaml() -> None:
    keys = ('viewer', 'operator', 'tenant_admin', 'deployer')
    documents = [capsule_cluster_role_manifest(get_access_profile(key, 1)) for key in keys]
    bundle = yaml.safe_dump_all(documents, sort_keys=False, explicit_start=True)
    loaded = list(yaml.safe_load_all(bundle))

    assert len(loaded) == len(keys) == 4
    assert loaded == documents
    assert [document['metadata']['name'] for document in loaded] == [
        'kaori-tenant-viewer-v1',
        'kaori-tenant-operator-v1',
        'kaori-tenant-tenant-admin-v1',
        'kaori-tenant-deployer-v1',
    ]
    assert all(document['kind'] == 'ClusterRole' for document in loaded)
    assert len(ACCESS_PROFILE_CATALOG) == 4
