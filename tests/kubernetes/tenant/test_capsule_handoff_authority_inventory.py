"""#1229 Capsule shared quota and RBAC provenance: authored-only regression cases.

No tests/gates/provider API calls are executed during source-review HOLD.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from app.kubernetes.tenant.capsule_handoff_authority_inventory import (
    inspect_capsule_role_binding_lineage,
    observe_capsule_global_quotas,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest, _role_contract_sha256, classify_capsule_related_resource,
)


def _quota(*, name='global-one', target='demo', uid='grq-uid', rv='3'):
    return {
        'metadata': {
            'name': name, 'uid': uid, 'resourceVersion': rv,
            'labels': {'app.kubernetes.io/managed-by': 'capsule'},
            'annotations': {'foreign.example/retained': 'yes'},
        },
        'spec': {
            'namespaceSelectors': [{
                'matchLabels': {'capsule.clastix.io/tenant': target},
            }],
            'quota': {'hard': {'requests.cpu': '2'}},
        },
    }


class _Custom:
    def __init__(self, *, items=None, version='7', continue_token='', status=None):
        self.items = items if items is not None else [_quota()]
        self.version = version
        self.continue_token = continue_token
        self.status = status
        self.calls = []

    def list_cluster_custom_object(self, group, version, plural, **kwargs):
        self.calls.append((group, version, plural, kwargs))
        if self.status == 'unavailable' or (self.status == 'fallback' and version == 'v1beta2'):
            raise ApiException(status=404)
        return {
            'metadata': {
                'resourceVersion': self.version,
                'continue': self.continue_token,
            },
            'items': deepcopy(self.items),
        }


def test_cluster_scoped_quotas_read_only_bounded_and_sha_bound():
    custom = _Custom(items=[_quota(), _quota(name='other', target='external', uid='u2')])
    evidence = observe_capsule_global_quotas(custom=custom, tenant_name='demo')
    assert evidence['status'] == 'observed_not_handoff_authorized'
    assert evidence['served_version'] == 'v1beta2'
    assert evidence['count'] == 2
    assert [item['scope'] for item in evidence['resources']] == [
        'direct_tenant_selector', 'other_tenant_selector',
    ]
    assert evidence['provider_mutation_performed'] is False
    assert evidence['provider_handoff_verified'] is False
    assert evidence['release_authorized'] is False
    assert custom.calls == [
        ('capsule.clastix.io', 'v1beta2', 'globalresourcequotas',
         {'limit': 101, '_request_timeout': 5}),
    ]
    assert 'requests.cpu' not in str(evidence)
    assert 'foreign.example/retained' not in str(evidence)


def test_global_quota_digest_tracks_full_policy_object_and_list_revision():
    obj = _quota()
    original = observe_capsule_global_quotas(custom=_Custom(items=[obj]), tenant_name='demo')
    drift = deepcopy(obj)
    drift['spec']['quota']['hard']['requests.cpu'] = '8'
    updated = observe_capsule_global_quotas(custom=_Custom(items=[drift]), tenant_name='demo')
    assert original['scope_sha256'] != updated['scope_sha256']
    updated_rv = observe_capsule_global_quotas(
        custom=_Custom(items=[obj], version='8'), tenant_name='demo',
    )
    assert original['scope_sha256'] != updated_rv['scope_sha256']
    shuffled = deepcopy(obj)
    shuffled['spec'] = dict(reversed(list(shuffled['spec'].items())))
    assert original['scope_sha256'] == observe_capsule_global_quotas(
        custom=_Custom(items=[shuffled]), tenant_name='demo',
    )['scope_sha256']


@pytest.mark.parametrize('scenario', [
    'unavailable', 'paginated', 'unbounded', 'missing_uid',
    'duplicate', 'malformed_spec', 'missing_list_rv',
])
def test_global_quota_missing_ambiguous_or_partial_evidence_fails_closed(scenario):
    client = _Custom()
    if scenario == 'unavailable':
        client.status = 'unavailable'
    elif scenario == 'paginated':
        client.continue_token = 'next'
    elif scenario == 'unbounded':
        client.items = [
            _quota(name=str(i), uid=str(i)) for i in range(101)
        ]
    elif scenario == 'missing_uid':
        client.items[0]['metadata']['uid'] = ''
    elif scenario == 'duplicate':
        client.items.append(deepcopy(client.items[0]))
    elif scenario == 'malformed_spec':
        client.items[0]['spec']['quota']['hard'] = {'cpu': float('nan')}
    elif scenario == 'missing_list_rv':
        client.version = ''
    with pytest.raises(ValueError):
        observe_capsule_global_quotas(custom=client, tenant_name='demo')


def test_global_quota_api_version_fallback_and_unverified_selectors():
    c = _Custom(status='fallback')
    evidence = observe_capsule_global_quotas(custom=c, tenant_name='demo')
    assert evidence['served_version'] == 'v1beta1'
    unbounded = _quota()
    unbounded['spec']['namespaceSelectors'] = [{
        'matchExpressions': [{
            'key': 'capsule.clastix.io/tenant', 'operator': 'In', 'values': ['demo'],
        }],
    }]
    evidence = observe_capsule_global_quotas(custom=_Custom(items=[unbounded]), tenant_name='demo')
    assert evidence['resources'][0]['scope'] == 'unverified_selector'
    assert evidence['blockers']


def _binding():
    return {
        'clusterRoleName': 'tenant-readonly',
        'subjects': [{
            'kind': 'User', 'name': 'private-user',
            'apiGroup': 'rbac.authorization.k8s.io',
        }],
        'labels': {
            'app.kubernetes.io/managed-by': 'kaori',
            'kaori.io/access-grant': 'grant-1',
            'kaori.io/tenant-id': 'tenant-1',
        },
    }


def _capsule_spec(*, names=None):
    return {
        'additionalRoleBindings': [],
        'rules': [{
            'namespaceSelector': {
                'matchExpressions': [{
                    'key': 'kubernetes.io/metadata.name',
                    'operator': 'In',
                    'values': names or ['demo-dev'],
                }],
            },
            'permissions': {'bindings': [_binding()]},
        }],
    }


def _related_record():
    value = {
        'kind': 'RoleBinding', 'origin': 'kaori_correlated',
        'namespace': 'demo-dev', 'name': 'generated-binding',
        'uid': 'rb-uid', 'resource_version': '19',
        'grant_scope_sha256': _digest({'namespace': 'demo-dev', 'grant': 'grant-1'}),
        'binding_contract_sha256': _role_contract_sha256(
            role='tenant-readonly', subjects=_binding()['subjects'],
            grant='grant-1', tenant='tenant-1',
        ),
    }
    return {'resources': [value], 'resource_count': 1}


def _lineage(spec=None, related=None):
    return inspect_capsule_role_binding_lineage(
        capsule_spec=spec if spec is not None else _capsule_spec(),
        related=related if related is not None else _related_record(),
        namespaces=[{'kind': 'Namespace', 'name': 'demo-dev', 'uid': 'ns-uid'}],
        tenant_id='tenant-1',
    )


def test_matching_intent_does_not_grant_controller_provenance_or_release():
    value = _lineage()
    assert value['intent_count'] == value['effective_kaori_count'] == 1
    assert value['contract_correlated'] is True
    assert value['controller_origin_verified'] is False
    assert value['status'] == 'contract_correlated_controller_origin_unverified'
    assert value['provider_mutation_performed'] is False
    assert value['release_authorized'] is False
    assert 'private-user' not in str(value)
    assert 'grant-1' not in str(value)


def test_matching_role_binding_requires_exact_manager_grant_tenant_and_subjects():
    source = SimpleNamespace(
        metadata=SimpleNamespace(
            name='generated-binding', uid='rb-uid', resource_version='19',
            namespace='demo-dev',
            labels={
                **_binding()['labels'],
                'capsule.clastix.io/tenant': 'demo',
            },
            annotations={},
            owner_references=[],
            finalizers=[],
        ),
        role_ref=SimpleNamespace(
            name='tenant-readonly', kind='ClusterRole', api_group='rbac.authorization.k8s.io',
        ),
        subjects=[SimpleNamespace(kind='User', name='private-user',
                                  api_group='rbac.authorization.k8s.io', namespace=None)],
    )
    evidence, blockers = classify_capsule_related_resource(
        resource=source, kind='RoleBinding', namespace='demo-dev',
        tenant_id='tenant-1', capsule_name='demo', capsule_uid='cr-uid',
    )
    assert evidence['grant_scope_sha256'] == _related_record()['resources'][0]['grant_scope_sha256']
    assert evidence['binding_contract_sha256'] == _related_record()['resources'][0]['binding_contract_sha256']
    assert blockers  # KAORI grant remains a Release blocker, even with matching provenance.


@pytest.mark.parametrize('mutation', [
    lambda s: s['rules'][0]['namespaceSelector'].update(matchLabels={'foreign': 'scope'}),
    lambda s: s['rules'][0]['namespaceSelector']['matchExpressions'][0].update(values=['other']),
    lambda s: s['rules'][0]['namespaceSelector']['matchExpressions'][0].update(operator='NotIn'),
    lambda s: s['rules'].append(deepcopy(s['rules'][0])),
    lambda s: s.update(rules='bad'),
])
def test_unbounded_duplicate_or_foreign_rbac_scope_fails_closed(mutation):
    spec = _capsule_spec()
    mutation(spec)
    with pytest.raises(ValueError):
        _lineage(spec=spec)


def test_unbounded_additional_role_bindings_are_blocked():
    spec = _capsule_spec()
    spec['additionalRoleBindings'] = [_binding()]
    item = _lineage(spec=spec)
    assert item['blockers']
    assert item['contract_correlated'] is False


def test_effective_role_drift_or_missing_binding_remains_blocked():
    changed = _related_record()
    changed['resources'][0]['binding_contract_sha256'] = 'e' * 64
    result = _lineage(related=changed)
    assert result['blockers']
    empty = _lineage(related={'resources': []})
    assert empty['blockers']


def test_preflight_binds_cluster_quota_and_rbac_lineage_to_capsule_fingerprint_only():
    source = Path('app/kubernetes/tenant/release_preflight.py').read_text()
    assert "capsule_cr['capsule_shared_quota_sha256']" in source
    assert "capsule_cr['capsule_rbac_lineage_sha256']" in source
    assert 'observe_capsule_global_quotas(' in source
    assert 'inspect_capsule_role_binding_lineage(' in source
    assert "'provider_handoff_verified': False" not in source  # Not an execution receipt
    assert 'Capsule controller-generated RoleBinding origins' in source
