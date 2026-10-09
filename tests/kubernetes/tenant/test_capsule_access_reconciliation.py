from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import access_provider, capsule_access_reconciliation as capsule
from app.kubernetes.tenant.access import get_access_profile


def _grant(scope='namespace', status='active'):
    tenant = SimpleNamespace(
        id='tenant-a',
        provider_key='capsule',
        provider_state='capsule',
        reconciliation_authority='capsule',
        provider_reference='payments',
    )
    membership = SimpleNamespace(
        tenant_id='tenant-a',
        principal_type='user',
        status='active',
        subject_name='alice',
        user=SimpleNamespace(is_active=True),
        group=None,
    )
    namespace = SimpleNamespace(
        namespace='payments-dev',
        ownership_status='adopted',
        environment=SimpleNamespace(tenant_id='tenant-a'),
    )
    return SimpleNamespace(
        public_id='11111111-2222-3333-4444-555555555555',
        tenant_id='tenant-a',
        tenant=tenant,
        membership=membership,
        scope_type=scope,
        namespace=namespace if scope == 'namespace' else None,
        environment=None,
        access_profile='viewer',
        access_profile_version=1,
        status=status,
        reconciliation_evidence_json=None,
    )


def test_capsule_binding_uses_exact_profile_and_immutable_namespace_selector():
    grant = _grant()
    binding = capsule._binding(grant, 'kaori-tenant-viewer-v1', ['payments-dev'])
    spec = capsule._update_spec({'owners': [{'name': 'root', 'kind': 'User'}]}, grant, binding, ['payments-dev'])
    assert spec['owners'] == [{'name': 'root', 'kind': 'User'}]
    assert spec['rules'][0]['namespaceSelector']['matchExpressions'] == [
        {'key': 'kubernetes.io/metadata.name', 'operator': 'In', 'values': ['payments-dev']}
    ]
    assert spec['rules'][0]['permissions']['bindings'][0] == binding
    assert capsule._update_spec(spec, grant, binding, ['payments-dev']) == spec


def test_capsule_tenant_scope_stays_in_additional_rolebindings():
    grant = _grant(scope='tenant')
    binding = capsule._binding(grant, 'kaori-tenant-viewer-v1', ['payments-dev'])
    spec = capsule._update_spec({'owners': [{'name': 'root'}]}, grant, binding, ['payments-dev'])
    assert spec['additionalRoleBindings'] == [binding]
    assert spec['rules'] == []


def test_capsule_revocation_only_removes_kaori_owned_entry_and_retains_foreign_rules():
    grant = _grant()
    managed = capsule._binding(grant, 'kaori-tenant-viewer-v1', ['payments-dev'])
    foreign = {'clusterRoleName': 'other-viewer', 'subjects': [{'kind': 'Group', 'name': 'external'}]}
    spec = {
        'owners': [{'name': 'root', 'kind': 'User'}],
        'additionalRoleBindings': [foreign],
        'rules': [
            {'namespaceSelector': {'matchLabels': {'team': 'payments'}}},
            {
                'namespaceSelector': {'matchLabels': {'team': 'payments'}},
                'permissions': {'bindings': [managed, foreign]},
            },
        ],
    }
    after = capsule._update_spec(spec, grant, None, [])
    assert after['owners'] == spec['owners']
    assert after['additionalRoleBindings'] == [foreign]
    assert after['rules'][0] == spec['rules'][0]
    assert after['rules'][1]['permissions']['bindings'] == [foreign]
    assert spec['rules'][1]['permissions']['bindings'][0] == managed


def test_capsule_duplicate_identity_and_collision_fail_closed():
    grant = _grant()
    managed = capsule._binding(grant, 'kaori-tenant-viewer-v1', ['payments-dev'])
    with pytest.raises(ValueError, match='Duplicate'):
        capsule._update_spec(
            {'additionalRoleBindings': [managed, managed]}, grant, managed, ['payments-dev']
        )
    with pytest.raises(ValueError, match='already has another'):
        capsule._update_spec(
            {'additionalRoleBindings': [
                {'clusterRoleName': 'kaori-tenant-viewer-v1', 'subjects': [{'kind': 'User', 'name': 'bob'}]}
            ]},
            grant, managed, ['payments-dev']
        )
    with pytest.raises(ValueError, match='foreign grant ownership'):
        capsule._update_spec(
            {'additionalRoleBindings': [{**managed, 'labels': {
                'kaori.io/access-grant': grant.public_id, 'app.kubernetes.io/managed-by': 'other'
            }}]},
            grant, managed, ['payments-dev']
        )


def test_profile_cluster_role_must_match_versioned_security_contract():
    grant = _grant()
    profile = get_access_profile('viewer')
    rules = [
        SimpleNamespace(api_groups=list(rule.api_groups), resources=list(rule.resources), verbs=list(rule.verbs),
                        resource_names=None, non_resource_urls=None)
        for rule in profile.rules
    ]
    role = SimpleNamespace(rules=rules, aggregation_rule=None)
    api = SimpleNamespace(read_cluster_role=lambda *args, **kwargs: role)
    assert capsule._check_profile(grant, api) == 'kaori-tenant-viewer-v1'
    role.aggregation_rule = SimpleNamespace()
    with pytest.raises(ValueError, match='aggregation'):
        capsule._check_profile(grant, api)
    role.aggregation_rule = None
    role.rules = rules[:-1]
    with pytest.raises(ValueError, match='does not match'):
        capsule._check_profile(grant, api)


def test_provider_dispatch_never_crosses_authority(monkeypatch):
    grant = _grant()
    monkeypatch.setattr(access_provider, 'reconcile_capsule_access_grant', lambda value: 'capsule')
    monkeypatch.setattr(access_provider, 'reconcile_native_access_grant', lambda value: 'native')
    assert access_provider.reconcile_provider_access_grant(grant) == 'capsule'
    grant.tenant.reconciliation_authority = 'native_kubernetes'
    with pytest.raises(ValueError, match='disagree'):
        access_provider.reconcile_provider_access_grant(grant)


def test_capsule_serviceaccount_cannot_expand_across_namespaces():
    grant = _grant(scope='tenant')
    grant.membership.principal_type = 'service_account'
    grant.membership.user = None
    with pytest.raises(ValueError, match='exactly one Namespace'):
        capsule._binding(grant, 'kaori-tenant-deployer-v1', ['payments-dev', 'payments-prod'])


def test_capsule_namespace_ownership_and_tenant_scope_are_fail_closed(monkeypatch):
    grant = _grant()
    target = grant.namespace
    monkeypatch.setattr(capsule, 'target_namespaces', lambda value: [target])
    labels = {'kubernetes.io/metadata.name': 'payments-dev', 'capsule.clastix.io/tenant': 'payments'}
    namespace = SimpleNamespace(metadata=SimpleNamespace(labels=labels))
    core = SimpleNamespace(read_namespace=lambda *args, **kwargs: namespace)
    client = SimpleNamespace(core_api=lambda: core)
    item = {'status': {'namespaces': ['payments-dev']}}
    assert capsule._namespaces(grant, client, item) == ['payments-dev']
    labels['capsule.clastix.io/tenant'] = 'another'
    with pytest.raises(ValueError, match='unverified'):
        capsule._namespaces(grant, client, item)
    labels['capsule.clastix.io/tenant'] = 'payments'
    grant.scope_type = 'tenant'
    with pytest.raises(ValueError, match='not yet governed'):
        capsule._namespaces(grant, client, {'status': {'namespaces': ['payments-dev', 'payments-prod']}})


def test_capsule_apply_requires_effective_rolebinding_not_only_successful_patch(monkeypatch):
    grant = _grant()
    target = grant.namespace
    monkeypatch.setattr(capsule, 'target_namespaces', lambda value: [target])
    monkeypatch.setattr(capsule, '_capability', lambda *args, **kwargs: 'v1beta2')
    item = {
        'metadata': {'name': 'payments', 'uid': 'capsule-uid', 'resourceVersion': '1'},
        'spec': {'owners': [{'name': 'root', 'kind': 'User'}]},
        'status': {'namespaces': ['payments-dev']},
    }
    profile = get_access_profile('viewer')
    rules = [
        SimpleNamespace(api_groups=list(rule.api_groups), resources=list(rule.resources), verbs=list(rule.verbs),
                        resource_names=None, non_resource_urls=None)
        for rule in profile.rules
    ]
    class Custom:
        api_client = None

        def get_cluster_custom_object(self, *args, **kwargs):
            return deepcopy(item)

        def patch_cluster_custom_object(self, *args, **kwargs):
            if kwargs.get('dry_run') != 'All':
                item['spec'].update(deepcopy(args[4]['spec']))
                item['metadata']['resourceVersion'] = '2'
            return deepcopy(item)

    class RBAC:
        def read_cluster_role(self, *args, **kwargs):
            return SimpleNamespace(rules=rules, aggregation_rule=None)

        def list_namespaced_role_binding(self, *args, **kwargs):
            return SimpleNamespace(items=[])

    ns = SimpleNamespace(metadata=SimpleNamespace(labels={
        'capsule.clastix.io/tenant': 'payments', 'kubernetes.io/metadata.name': 'payments-dev'
    }))
    client = SimpleNamespace(
        custom_objects_api=lambda: Custom(),
        rbac_authorization_api=lambda: RBAC(),
        core_api=lambda: SimpleNamespace(read_namespace=lambda *args, **kwargs: ns),
    )
    monkeypatch.setattr(capsule, '_context', lambda _: (client, 'payments', 'tenant-a'))
    result = capsule.reconcile_capsule_access_grant(grant)
    assert result.reconciliation_status == 'drifted'
    assert result.reconciliation_evidence_json['effective_targets'] == []
    assert item['spec']['rules'][0]['permissions']['bindings'][0]['labels']['kaori.io/access-grant'] == grant.public_id
