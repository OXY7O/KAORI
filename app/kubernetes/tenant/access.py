from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import TenantAccessGrant, TenantMembership


class TenantAccessProfileKey(StrEnum):
    VIEWER = 'viewer'
    OPERATOR = 'operator'
    TENANT_ADMIN = 'tenant_admin'
    DEPLOYER = 'deployer'


class TenantAccessScope(StrEnum):
    TENANT = 'tenant'
    ENVIRONMENT = 'environment'
    NAMESPACE = 'namespace'


@dataclass(frozen=True, slots=True)
class TenantRbacRule:
    api_groups: tuple[str, ...]
    resources: tuple[str, ...]
    verbs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TenantAccessProfile:
    key: TenantAccessProfileKey
    version: int
    label: str
    rules: tuple[TenantRbacRule, ...]


_READ = ('get', 'list', 'watch')
_WRITE = ('create', 'delete', 'patch', 'update')
_WORKLOADS = ('deployments', 'deployments/scale', 'statefulsets', 'statefulsets/scale', 'daemonsets', 'replicasets')
_BATCH = ('jobs', 'cronjobs')
_SERVICE_DATA = ('services', 'configmaps', 'persistentvolumeclaims')
_FORBIDDEN_RESOURCES = frozenset(
    {
        '*',
        'clusterrolebindings',
        'clusterroles',
        'customresourcedefinitions',
        'limitranges',
        'namespaces',
        'nodes',
        'persistentvolumes',
        'resourcequotas',
        'rolebindings',
        'roles',
        'storageclasses',
        'mutatingwebhookconfigurations',
        'validatingwebhookconfigurations',
    }
)


def _rule(api_group: str, resources: tuple[str, ...], verbs: tuple[str, ...]) -> TenantRbacRule:
    return TenantRbacRule(api_groups=(api_group,), resources=resources, verbs=verbs)


_VIEWER_RULES = (
    _rule('', ('pods', 'services', 'endpoints', 'configmaps', 'persistentvolumeclaims', 'events'), _READ),
    _rule('', ('pods/log',), ('get',)),
    _rule('', ('resourcequotas', 'limitranges', 'serviceaccounts'), _READ),
    _rule('apps', _WORKLOADS, _READ),
    _rule('batch', _BATCH, _READ),
    _rule('networking.k8s.io', ('ingresses', 'networkpolicies'), _READ),
    _rule('autoscaling', ('horizontalpodautoscalers',), _READ),
)

_OPERATOR_RULES = _VIEWER_RULES + (
    _rule('', ('pods',), ('delete', 'get', 'list', 'watch')),
    _rule('', ('pods/exec', 'pods/portforward'), ('create',)),
    _rule('', _SERVICE_DATA, _READ + _WRITE),
    _rule('apps', _WORKLOADS, _READ + _WRITE),
    _rule('batch', _BATCH, _READ + _WRITE),
    _rule('networking.k8s.io', ('ingresses',), _READ + _WRITE),
    _rule('autoscaling', ('horizontalpodautoscalers',), _READ + _WRITE),
)

_TENANT_ADMIN_RULES = _OPERATOR_RULES + (
    _rule('', ('secrets',), _READ + _WRITE),
)

_DEPLOYER_RULES = (
    _rule('', ('pods', 'services', 'configmaps', 'persistentvolumeclaims', 'secrets'), _READ),
    _rule('', ('services', 'configmaps', 'persistentvolumeclaims', 'secrets'), _WRITE),
    _rule('apps', _WORKLOADS, _READ + _WRITE),
    _rule('batch', _BATCH, _READ + _WRITE),
    _rule('networking.k8s.io', ('ingresses',), _READ + _WRITE),
    _rule('autoscaling', ('horizontalpodautoscalers',), _READ + _WRITE),
)

ACCESS_PROFILE_CATALOG: dict[tuple[str, int], TenantAccessProfile] = {
    ('viewer', 1): TenantAccessProfile(
        key=TenantAccessProfileKey.VIEWER,
        version=1,
        label='Viewer',
        rules=_VIEWER_RULES,
    ),
    ('operator', 1): TenantAccessProfile(
        key=TenantAccessProfileKey.OPERATOR,
        version=1,
        label='Operator',
        rules=_OPERATOR_RULES,
    ),
    ('tenant_admin', 1): TenantAccessProfile(
        key=TenantAccessProfileKey.TENANT_ADMIN,
        version=1,
        label='Tenant Admin',
        rules=_TENANT_ADMIN_RULES,
    ),
    ('deployer', 1): TenantAccessProfile(
        key=TenantAccessProfileKey.DEPLOYER,
        version=1,
        label='Deployer',
        rules=_DEPLOYER_RULES,
    ),
}
LATEST_ACCESS_PROFILE_VERSION = {
    key: max(version for profile_key, version in ACCESS_PROFILE_CATALOG if profile_key == key)
    for key in {profile_key for profile_key, _ in ACCESS_PROFILE_CATALOG}
}


def validate_access_profile(profile: TenantAccessProfile) -> None:
    if profile.version < 1:
        raise ValueError('Tenant Access Profile version must be positive.')
    for rule in profile.rules:
        if '*' in rule.api_groups or '*' in rule.verbs:
            raise ValueError('Tenant Access Profiles cannot use wildcard API groups or verbs.')
        forbidden = _FORBIDDEN_RESOURCES.intersection(rule.resources)
        if forbidden:
            raise ValueError(
                'Tenant Access Profiles cannot grant platform or cluster-scoped resources: '
                + ', '.join(sorted(forbidden))
            )


def get_access_profile(key: str, version: int | None = None) -> TenantAccessProfile:
    normalized = key.strip().lower()
    selected_version = version if version is not None else LATEST_ACCESS_PROFILE_VERSION.get(normalized)
    if selected_version is None:
        raise ValueError('Select a supported Tenant Access Profile.')
    profile = ACCESS_PROFILE_CATALOG.get((normalized, selected_version))
    if profile is None:
        raise ValueError('The selected Tenant Access Profile version is unavailable.')
    validate_access_profile(profile)
    return profile


def validate_grant_scope(grant: TenantAccessGrant) -> None:
    membership = grant.membership
    if membership.tenant_id != grant.tenant_id:
        raise ValueError('Tenant Access Grant membership must belong to the selected Tenant.')

    scope = TenantAccessScope(grant.scope_type)
    if scope is TenantAccessScope.TENANT:
        if grant.environment is not None or grant.namespace is not None:
            raise ValueError('Tenant-scoped Access Grant cannot reference environment or namespace scope.')
        return

    if scope is TenantAccessScope.ENVIRONMENT:
        if grant.environment is None or grant.namespace is not None:
            raise ValueError('Environment-scoped Access Grant requires exactly one Tenant environment.')
        if grant.environment.tenant_id != grant.tenant_id:
            raise ValueError('Tenant Access Grant environment belongs to another Tenant.')
        return

    if grant.namespace is None or grant.environment is not None:
        raise ValueError('Namespace-scoped Access Grant requires exactly one managed namespace.')
    if grant.namespace.environment.tenant_id != grant.tenant_id:
        raise ValueError('Tenant Access Grant namespace belongs to another Tenant.')


def membership_subject(membership: TenantMembership) -> tuple[str, str]:
    if membership.status != 'active':
        raise ValueError('Tenant membership is not active.')

    subject_name = str(membership.subject_name or '').strip()
    if not subject_name:
        raise ValueError('Tenant membership requires a Kubernetes subject identity.')

    if membership.principal_type == 'user':
        user = membership.user
        if user is None or not user.is_active:
            raise ValueError('Tenant user membership requires an active KAORI user.')
        return 'User', subject_name

    if membership.principal_type == 'group':
        group = membership.group
        if group is None or not group.enabled:
            raise ValueError('Tenant group membership requires an enabled Tenant Group.')
        if group.tenant_id != membership.tenant_id:
            raise ValueError('Tenant group membership cannot cross Tenant boundaries.')
        return 'Group', subject_name

    raise ValueError('Unsupported Tenant membership principal type.')


def validate_active_grant(grant: TenantAccessGrant) -> TenantAccessProfile:
    validate_grant_scope(grant)
    if grant.status != 'active':
        raise ValueError('Tenant Access Grant is not active.')
    membership_subject(grant.membership)
    return get_access_profile(grant.access_profile, grant.access_profile_version)


for _profile in ACCESS_PROFILE_CATALOG.values():
    validate_access_profile(_profile)
