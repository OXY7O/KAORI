from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.access import (
    ACCESS_PROFILE_CATALOG,
    get_access_profile,
    membership_subject,
    validate_access_profile,
    validate_grant_scope,
)


def _resource_names(profile_key: str) -> set[str]:
    profile = get_access_profile(profile_key)
    return {resource for rule in profile.rules for resource in rule.resources}


def _verbs_for_resource(profile_key: str, resource: str) -> set[str]:
    return {
        verb
        for rule in get_access_profile(profile_key).rules
        if resource in rule.resources
        for verb in rule.verbs
    }


def test_canonical_access_profiles_are_versioned_and_explicit() -> None:
    assert set(ACCESS_PROFILE_CATALOG) == {
        ('viewer', 1),
        ('operator', 1),
        ('tenant_admin', 1),
        ('deployer', 1),
    }
    for profile in ACCESS_PROFILE_CATALOG.values():
        validate_access_profile(profile)
        assert all('*' not in rule.api_groups for rule in profile.rules)
        assert all('*' not in rule.resources for rule in profile.rules)
        assert all('*' not in rule.verbs for rule in profile.rules)


def test_viewer_is_read_only_and_cannot_read_secrets() -> None:
    assert _verbs_for_resource('viewer', 'pods') == {'get', 'list', 'watch'}
    assert 'secrets' not in _resource_names('viewer')


def test_operator_has_interactive_troubleshooting_without_security_admin() -> None:
    assert _verbs_for_resource('operator', 'pods/exec') == {'create'}
    assert _verbs_for_resource('operator', 'pods/portforward') == {'create'}
    resources = _resource_names('operator')
    assert not {'roles', 'rolebindings', 'serviceaccounts', 'namespaces'} & resources


def test_tenant_admin_does_not_gain_platform_security_controls() -> None:
    resources = _resource_names('tenant_admin')
    assert 'secrets' in resources
    assert not {'roles', 'rolebindings', 'namespaces'} & resources
    assert _verbs_for_resource('tenant_admin', 'resourcequotas') == {'get', 'list', 'watch'}
    assert _verbs_for_resource('tenant_admin', 'limitranges') == {'get', 'list', 'watch'}
    assert _verbs_for_resource('tenant_admin', 'serviceaccounts') == {'get', 'list', 'watch'}


def test_deployer_excludes_interactive_and_rbac_privileges() -> None:
    resources = _resource_names('deployer')
    assert 'deployments' in resources
    assert 'secrets' in resources
    assert not {'pods/exec', 'pods/portforward', 'pods/log', 'roles', 'rolebindings', 'namespaces'} & resources


def test_membership_subject_fails_closed_for_inactive_user() -> None:
    membership = SimpleNamespace(
        status='active',
        principal_type='user',
        subject_name='alice',
        user=SimpleNamespace(is_active=False),
        group=None,
        tenant_id='tenant-a',
    )
    with pytest.raises(ValueError, match='active KAORI user'):
        membership_subject(membership)


def test_grant_scope_rejects_cross_tenant_namespace() -> None:
    grant = SimpleNamespace(
        membership=SimpleNamespace(tenant_id='tenant-a'),
        tenant_id='tenant-a',
        scope_type='namespace',
        environment=None,
        namespace=SimpleNamespace(environment=SimpleNamespace(tenant_id='tenant-b')),
    )
    with pytest.raises(ValueError, match='another Tenant'):
        validate_grant_scope(grant)


def test_platform_managed_namespace_resources_remain_read_only() -> None:
    for profile_key in ('viewer', 'operator', 'tenant_admin'):
        for resource in ('resourcequotas', 'limitranges', 'serviceaccounts'):
            assert _verbs_for_resource(profile_key, resource) == {'get', 'list', 'watch'}


def test_unknown_access_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match='supported Tenant Access Profile'):
        get_access_profile('cluster-admin')
