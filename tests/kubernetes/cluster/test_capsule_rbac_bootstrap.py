from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from app.kubernetes.cluster import capsule_rbac_bootstrap as bootstrap
from app.kubernetes.tenant.access import capsule_cluster_role_manifest, get_access_profile


def _role(profile, *, drift=False, aggregated=False):
    source = capsule_cluster_role_manifest(profile)
    rules = [
        SimpleNamespace(
            to_dict=lambda rule=rule: {
                'api_groups': list(rule['apiGroups']),
                'resources': list(rule['resources']),
                'verbs': list(rule['verbs']),
            }
        )
        for rule in source['rules']
    ]
    if drift:
        rules[0] = SimpleNamespace(
            to_dict=lambda: {'api_groups': [''], 'resources': ['*'], 'verbs': ['*']}
        )
    return SimpleNamespace(
        rules=rules,
        aggregation_rule=SimpleNamespace() if aggregated else None,
        metadata=SimpleNamespace(uid='role-uid', resource_version='7'),
    )


class FakeRBAC:
    def __init__(self, roles=None, fail_on=None):
        self.roles = dict(roles or {})
        self.calls = []
        self.fail_on = fail_on

    def read_cluster_role(self, name, **kwargs):
        if name not in self.roles:
            raise ApiException(status=404)
        return self.roles[name]

    def create_cluster_role(self, body, **kwargs):
        name = body.metadata.name
        self.calls.append((name, kwargs.get('dry_run')))
        if self.fail_on == name and kwargs.get('dry_run') != 'All':
            raise ApiException(status=403)
        if name in self.roles:
            raise ApiException(status=409)
        if kwargs.get('dry_run') != 'All':
            self.roles[name] = SimpleNamespace(
                rules=body.rules, aggregation_rule=None,
                metadata=SimpleNamespace(uid='created-uid', resource_version='1'),
            )


def _evidence():
    return {
        'operation': 'check',
        'status': 'missing',
        'checked_at': datetime.now(UTC).isoformat(),
    }


def test_catalog_is_four_latest_canonical_profiles():
    assert [(x.key.value, x.version) for x in bootstrap._catalog()] == [
        ('viewer', 1), ('operator', 1), ('tenant_admin', 1), ('deployer', 1)
    ]


def test_existing_clusterrole_must_have_exact_permissions_and_no_aggregation():
    profile = get_access_profile('viewer', 1)
    name = bootstrap.capsule_cluster_role_name(profile)
    assert bootstrap._role_status(FakeRBAC(), profile)['status'] == 'missing'
    assert bootstrap._role_status(FakeRBAC({name: _role(profile)}), profile)['status'] == 'ready'
    assert bootstrap._role_status(FakeRBAC({name: _role(profile, drift=True)}), profile)['status'] == 'conflict'
    assert bootstrap._role_status(FakeRBAC({name: _role(profile, aggregated=True)}), profile)['status'] == 'conflict'


def test_bootstrap_only_creates_missing_roles_after_server_dry_run(monkeypatch):
    profiles = bootstrap._catalog()
    viewer = profiles[0]
    api = FakeRBAC({bootstrap.capsule_cluster_role_name(viewer): _role(viewer)})
    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: _evidence())
    monkeypatch.setattr(bootstrap, '_read_roles', lambda _: (
        api, [bootstrap._role_status(api, profile) for profile in profiles]
    ))
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'operation': action, 'status': status, **data
    })

    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)

    assert result['status'] == 'ready'
    assert len(result['created']) == 3
    assert len(api.calls) == 6
    assert result['created'] == ['kaori-tenant-operator-v1', 'kaori-tenant-tenant-admin-v1', 'kaori-tenant-deployer-v1']
    assert all(value == 'All' for _, value in api.calls[:3])
    assert all(value is None for _, value in api.calls[3:])
    assert bootstrap.capsule_cluster_role_name(viewer) not in result['created']
    assert result['ready'] == 4


def test_conflict_blocks_all_mutations(monkeypatch):
    profiles = bootstrap._catalog()
    name = bootstrap.capsule_cluster_role_name(profiles[0])
    api = FakeRBAC({name: _role(profiles[0], drift=True)})
    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: _evidence())
    monkeypatch.setattr(bootstrap, '_read_roles', lambda _: (
        api, [bootstrap._role_status(api, profile) for profile in profiles]
    ))
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'status': status, **data
    })

    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)
    assert result['status'] == 'failed'
    assert not api.calls
    assert result['conflict'] == 1


def test_partial_failure_preserves_created_roles_and_audit(monkeypatch):
    profiles = bootstrap._catalog()
    second_name = bootstrap.capsule_cluster_role_name(profiles[1])
    api = FakeRBAC(fail_on=second_name)
    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: _evidence())
    monkeypatch.setattr(bootstrap, '_read_roles', lambda _: (
        api, [bootstrap._role_status(api, profile) for profile in profiles]
    ))
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'status': status, **data
    })

    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)

    assert result['status'] == 'failed'
    assert result['partial'] is True
    assert result['created'] == ['kaori-tenant-viewer-v1']
    assert result['missing'] == 3


def test_bootstrap_requires_explicit_approval_and_fresh_check(monkeypatch):
    with pytest.raises(ValueError, match='approval'):
        bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=False)

    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: None)
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'status': status, **data
    })
    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)
    assert result['status'] == 'failed'
    assert result['created'] == []


def test_created_role_has_only_canonical_permissions_and_never_clusterrolebinding():
    for profile in bootstrap._catalog():
        body = bootstrap._body(profile)
        assert body.metadata.name == bootstrap.capsule_cluster_role_name(profile)
        assert body.metadata.labels['app.kubernetes.io/managed-by'] == 'kaori'
        assert len(body.rules) == len(profile.rules)
        assert all(
            rule.verbs == list(expected.verbs)
            for rule, expected in zip(body.rules, profile.rules, strict=True)
        )


def test_existing_all_exact_roles_require_no_mutation(monkeypatch):
    profiles = bootstrap._catalog()
    api = FakeRBAC({
        bootstrap.capsule_cluster_role_name(profile): _role(profile)
        for profile in profiles
    })
    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: _evidence())
    monkeypatch.setattr(bootstrap, '_read_roles', lambda _: (
        api, [bootstrap._role_status(api, profile) for profile in profiles]
    ))
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'status': status, **data
    })

    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)
    assert result['status'] == 'ready'
    assert result['ready'] == 4
    assert result['created'] == []
    assert api.calls == []


def test_bootstrap_rejects_stale_preflight_without_kubernetes_mutation(monkeypatch):
    monkeypatch.setattr(bootstrap, 'latest_capsule_role_bootstrap_evidence', lambda _: {
        'operation': 'check', 'status': 'missing', 'checked_at': '2020-01-01T00:00:00+00:00'
    })
    monkeypatch.setattr(bootstrap, '_audit', lambda cluster, actor, action, status, data: {
        'status': status, **data
    })
    result = bootstrap.bootstrap_missing_capsule_roles('cluster-a', 42, approved=True)
    assert result['status'] == 'failed'
    assert result['created'] == []
    assert 'stale' in result['reason']
