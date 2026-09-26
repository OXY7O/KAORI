from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import server_for_cluster
from app.kubernetes.tenant.access import validate_active_grant, validate_grant_scope
from app.kubernetes.tenant.access_reconciliation import target_namespaces
from app.models import Cluster
from app.models.tenant import (
    TenantAccessScope,
    TenantCredential,
    TenantCredentialDeliveryMethod,
    TenantCredentialStatus,
    TenantCredentialType,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)

DEFAULT_CREDENTIAL_VALIDITY_DAYS = 365
DEFAULT_RENEWAL_WINDOW_DAYS = 30
DEFAULT_TOKEN_TTL_SECONDS = 3600
_MIN_TOKEN_TTL_SECONDS = 300
_MAX_TOKEN_TTL_SECONDS = 3600
_PURPOSE_RE = re.compile(r'[^a-z0-9-]+')


@dataclass(frozen=True, slots=True)
class NamespaceAccessPackage:
    tenant_id: str
    tenant_name: str
    environment: str
    namespace: str
    cluster_id: str
    cluster_name: str
    api_endpoint: str
    access_profile: str
    access_profile_version: int | None
    application_name: str | None
    purpose: str
    approved_access_methods: tuple[str, ...]
    credential_public_id: str
    credential_type: str
    credential_status: str
    service_account_name: str
    jumpserver_reference: str | None
    valid_until: datetime
    renewal_due_at: datetime
    rotation_generation: int
    actions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'environment': self.environment,
            'namespace': self.namespace,
            'cluster_id': self.cluster_id,
            'cluster_name': self.cluster_name,
            'api_endpoint': self.api_endpoint,
            'access_profile': self.access_profile,
            'access_profile_version': self.access_profile_version,
            'application_name': self.application_name,
            'purpose': self.purpose,
            'approved_access_methods': list(self.approved_access_methods),
            'credential_public_id': self.credential_public_id,
            'credential_type': self.credential_type,
            'credential_status': self.credential_status,
            'service_account_name': self.service_account_name,
            'jumpserver_reference': self.jumpserver_reference,
            'valid_until': self.valid_until.isoformat(),
            'renewal_due_at': self.renewal_due_at.isoformat(),
            'rotation_generation': self.rotation_generation,
            'actions': list(self.actions),
        }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_credential_purpose(value: str) -> str:
    purpose = _PURPOSE_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    purpose = re.sub(r'-+', '-', purpose).strip('-')
    if not purpose or len(purpose) > 120:
        raise ValueError('Tenant credential purpose must contain 1–120 lowercase letters, numbers, or hyphens.')
    return purpose


def normalize_deployer_application(value: str) -> str:
    application = _PURPOSE_RE.sub('-', value.strip().lower().replace('_', '-').replace(' ', '-'))
    application = re.sub(r'-+', '-', application).strip('-')
    if not application or len(application) > 63:
        raise ValueError('Tenant deployer application must contain 1–63 lowercase letters, numbers, or hyphens.')
    return application


def effective_credential_status(
    credential: TenantCredential,
    *,
    now: datetime | None = None,
) -> str:
    current = _aware(now or datetime.now(UTC))
    status = TenantCredentialStatus(credential.status)
    if status in {
        TenantCredentialStatus.REVOKED,
        TenantCredentialStatus.SUSPENDED,
        TenantCredentialStatus.ROTATING,
    }:
        return status.value
    if current >= _aware(credential.valid_until):
        return TenantCredentialStatus.EXPIRED.value
    if current >= _aware(credential.renewal_due_at):
        return TenantCredentialStatus.RENEWAL_DUE.value
    return TenantCredentialStatus.ACTIVE.value


def refresh_credential_status(
    credential: TenantCredential,
    *,
    now: datetime | None = None,
) -> str:
    status = effective_credential_status(credential, now=now)
    credential.status = status
    return status


def credential_target_namespaces(credential: TenantCredential) -> list[TenantNamespace]:
    credential_type = TenantCredentialType(credential.credential_type)
    if credential_type in {
        TenantCredentialType.HUMAN_SERVICE_ACCOUNT,
        TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT,
    }:
        if credential.access_grant is None:
            raise ValueError('Tenant ServiceAccount credential requires an Access Grant.')
        return target_namespaces(credential.access_grant)

    if credential.anchor_namespace is None:
        raise ValueError('Administrative Tenant credential requires an anchor namespace.')
    return [credential.anchor_namespace]


def _is_active_lifecycle(status: str) -> bool:
    return status in {
        TenantCredentialStatus.ACTIVE.value,
        TenantCredentialStatus.RENEWAL_DUE.value,
        TenantCredentialStatus.ROTATING.value,
    }


def _validate_common_credential(credential: TenantCredential) -> bool:
    owner = credential.owner_user
    if owner is None:
        raise ValueError('Tenant credential requires an owner.')

    active_lifecycle = _is_active_lifecycle(credential.status)
    if active_lifecycle and not owner.is_active:
        raise ValueError('Active Tenant credential requires an active owner.')

    if credential.tenant is None:
        raise ValueError('Tenant credential requires a Tenant.')
    if credential.tenant.provider_key != 'native_kubernetes':
        raise ValueError('This credential lifecycle currently requires Native Kubernetes provider authority.')

    if not credential.purpose or credential.purpose != normalize_credential_purpose(credential.purpose):
        raise ValueError('Tenant credential purpose is not normalized.')
    if _aware(credential.valid_from) >= _aware(credential.valid_until):
        raise ValueError('Tenant credential validity window is invalid.')
    if not (_aware(credential.valid_from) <= _aware(credential.renewal_due_at) <= _aware(credential.valid_until)):
        raise ValueError('Tenant credential renewal window is invalid.')
    return active_lifecycle


def _validate_exceptional_kubeconfig(credential: TenantCredential) -> None:
    approver = credential.exception_authorized_by
    if approver is None or not approver.is_active or not approver.is_admin_level:
        raise ValueError('Exceptional kubeconfig delivery requires an active KAORI administrator approval.')
    if not (credential.exception_reason or '').strip():
        raise ValueError('Exceptional kubeconfig delivery requires an approval reason.')
    if credential.exception_valid_until is None:
        raise ValueError('Exceptional kubeconfig delivery requires an expiry.')
    if _aware(credential.exception_valid_until) > _aware(credential.valid_until):
        raise ValueError('Exceptional kubeconfig approval cannot outlive the credential entitlement.')


def _validate_human_credential(
    credential: TenantCredential,
    *,
    active_lifecycle: bool,
    delivery: TenantCredentialDeliveryMethod,
) -> None:
    grant = credential.access_grant
    if grant is None:
        raise ValueError('Human Tenant credential requires an Access Grant.')

    validate_grant_scope(grant)
    if grant.tenant_id != credential.tenant_id:
        raise ValueError('Tenant credential Access Grant belongs to another Tenant.')
    if grant.membership.principal_type != 'user' or grant.membership.user_id != credential.owner_user_id:
        raise ValueError('Human Tenant credential must be individually owned by the Access Grant user.')
    if grant.access_profile == 'deployer':
        raise ValueError('Human Tenant credentials cannot use the machine-only Deployer Access Profile.')
    if active_lifecycle:
        validate_active_grant(grant)

    allowed_delivery = {
        TenantCredentialDeliveryMethod.JUMPSERVER,
        TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG,
    }
    if delivery not in allowed_delivery:
        raise ValueError('Human Tenant credential requires JumpServer or governed exceptional kubeconfig delivery.')
    if not (credential.jumpserver_reference or '').strip():
        raise ValueError('Human Tenant credential requires a non-secret JumpServer reference.')
    if delivery is TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG:
        _validate_exceptional_kubeconfig(credential)


def _validate_deployer_credential(
    credential: TenantCredential,
    *,
    active_lifecycle: bool,
    delivery: TenantCredentialDeliveryMethod,
) -> None:
    if delivery is not TenantCredentialDeliveryMethod.CICD_KUBECONFIG:
        raise ValueError('Deployer Tenant credential requires CI/CD kubeconfig delivery.')
    grant = credential.access_grant
    if grant is None:
        raise ValueError('Deployer Tenant credential requires a Deployer Access Grant.')
    if grant.access_profile != 'deployer':
        raise ValueError('Deployer Tenant credential requires the Deployer Access Profile.')
    if grant.scope_type != TenantAccessScope.NAMESPACE.value:
        raise ValueError('Deployer Tenant credential requires a namespace-scoped Access Grant.')
    if grant.namespace is None or grant.namespace.environment.tenant_id != credential.tenant_id:
        raise ValueError('Deployer Tenant credential namespace belongs to another Tenant.')
    if grant.membership.principal_type != 'service_account':
        raise ValueError('Deployer Tenant credential requires a ServiceAccount Tenant membership.')
    application_name = normalize_deployer_application(credential.application_name or '')
    if application_name != credential.application_name:
        raise ValueError('Tenant deployer application name is not normalized.')
    if grant.membership.subject_name != credential.service_account_name:
        raise ValueError('Deployer credential ServiceAccount must match its machine Access Grant membership.')
    if active_lifecycle:
        validate_active_grant(grant)


def _validate_admin_credential(
    credential: TenantCredential,
    *,
    active_lifecycle: bool,
    delivery: TenantCredentialDeliveryMethod,
) -> None:
    if delivery is not TenantCredentialDeliveryMethod.ADMIN_KUBECONFIG:
        raise ValueError('Administrative Tenant credential requires admin kubeconfig delivery.')
    if active_lifecycle and not credential.owner_user.is_admin_level:
        raise ValueError('Active administrative kubeconfig ownership requires a KAORI administrator.')

    namespace = credential.anchor_namespace
    if namespace is None:
        raise ValueError('Administrative Tenant credential requires an anchor namespace.')
    if namespace.environment.tenant_id != credential.tenant_id:
        raise ValueError('Administrative credential anchor namespace belongs to another Tenant.')
    if namespace.cluster_id != credential.tenant.cluster_id:
        raise ValueError('Administrative credential anchor namespace belongs to another cluster.')


def _validate_target_readiness(
    credential: TenantCredential,
    *,
    active_lifecycle: bool,
) -> None:
    targets = credential_target_namespaces(credential)
    if not targets:
        raise ValueError('Tenant credential has no managed namespace target.')
    if not active_lifecycle:
        return
    for namespace in targets:
        if namespace.provisioning_status != TenantNamespaceProvisioningStatus.READY.value:
            raise ValueError('Tenant credential targets must be Ready managed namespaces.')


def validate_credential_contract(credential: TenantCredential) -> None:
    active_lifecycle = _validate_common_credential(credential)
    delivery = TenantCredentialDeliveryMethod(credential.delivery_method)
    credential_type = TenantCredentialType(credential.credential_type)

    if credential_type is TenantCredentialType.HUMAN_SERVICE_ACCOUNT:
        _validate_human_credential(
            credential,
            active_lifecycle=active_lifecycle,
            delivery=delivery,
        )
    elif credential_type is TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT:
        _validate_deployer_credential(
            credential,
            active_lifecycle=active_lifecycle,
            delivery=delivery,
        )
    else:
        _validate_admin_credential(
            credential,
            active_lifecycle=active_lifecycle,
            delivery=delivery,
        )
    _validate_target_readiness(credential, active_lifecycle=active_lifecycle)


def token_ttl_seconds(
    credential: TenantCredential,
    *,
    requested_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    now: datetime | None = None,
) -> int:
    status = effective_credential_status(credential, now=now)
    if status not in {TenantCredentialStatus.ACTIVE.value, TenantCredentialStatus.RENEWAL_DUE.value}:
        raise ValueError('Tenant credential is not active for credential material issuance.')

    current = _aware(now or datetime.now(UTC))
    remaining = int((_aware(credential.valid_until) - current).total_seconds())
    if credential.delivery_method == TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG.value:
        if credential.exception_valid_until is None or current >= _aware(credential.exception_valid_until):
            raise ValueError('Exceptional kubeconfig approval is expired.')
        remaining = min(remaining, int((_aware(credential.exception_valid_until) - current).total_seconds()))

    bounded = min(max(int(requested_seconds), _MIN_TOKEN_TTL_SECONDS), _MAX_TOKEN_TTL_SECONDS, remaining)
    if bounded < _MIN_TOKEN_TTL_SECONDS:
        raise ValueError('Tenant credential validity is too close to expiry to issue new credential material.')
    return bounded


def build_namespace_access_package(
    credential: TenantCredential,
    namespace: TenantNamespace,
) -> NamespaceAccessPackage:
    validate_credential_contract(credential)
    targets = {item.id: item for item in credential_target_namespaces(credential)}
    if namespace.id not in targets:
        raise ValueError('Namespace is outside this Tenant credential scope.')

    cluster = db.session.get(Cluster, credential.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')

    if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
        profile = credential.access_grant.access_profile if credential.access_grant is not None else 'unknown'
        profile_version = (
            credential.access_grant.access_profile_version if credential.access_grant is not None else None
        )
        methods = ('jumpserver',)
        if credential.delivery_method == TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG.value:
            methods = ('jumpserver', 'exceptional_kubeconfig')
    elif credential.credential_type == TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT.value:
        profile = credential.access_grant.access_profile if credential.access_grant is not None else 'unknown'
        profile_version = (
            credential.access_grant.access_profile_version if credential.access_grant is not None else None
        )
        methods = ('cicd_kubeconfig',)
    else:
        profile = 'cluster-admin'
        profile_version = None
        methods = ('admin_kubeconfig',)

    status = effective_credential_status(credential)
    actions = ['revoke']
    if status in {TenantCredentialStatus.ACTIVE.value, TenantCredentialStatus.RENEWAL_DUE.value}:
        actions = ['rotate', 'suspend', 'revoke']
    elif status == TenantCredentialStatus.SUSPENDED.value:
        actions = ['resume', 'revoke']

    return NamespaceAccessPackage(
        tenant_id=credential.tenant_id,
        tenant_name=credential.tenant.name,
        environment=namespace.environment.environment,
        namespace=namespace.namespace,
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        api_endpoint=server_for_cluster(cluster),
        access_profile=profile,
        access_profile_version=profile_version,
        application_name=credential.application_name,
        purpose=credential.purpose,
        approved_access_methods=methods,
        credential_public_id=credential.public_id,
        credential_type=credential.credential_type,
        credential_status=status,
        service_account_name=credential.service_account_name,
        jumpserver_reference=credential.jumpserver_reference,
        valid_until=_aware(credential.valid_until),
        renewal_due_at=_aware(credential.renewal_due_at),
        rotation_generation=credential.rotation_generation,
        actions=tuple(actions),
    )
