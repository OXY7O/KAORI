from __future__ import annotations

import uuid
from dataclasses import dataclass

from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.tenant.access import get_access_profile, validate_active_grant
from app.kubernetes.tenant.access_reconciliation import reconcile_native_access_grant
from app.kubernetes.tenant.credential import (
    DEFAULT_CREDENTIAL_VALIDITY_DAYS,
    normalize_credential_purpose,
    normalize_deployer_application,
    validate_credential_contract,
)
from app.kubernetes.tenant.credential_reconciliation import reconcile_native_credential
from app.kubernetes.tenant.credential_service import (
    TenantCredentialStateConflictError,
    _record_event,
    _record_generation,
    _validity_window,
)
from app.models import User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantAccessGrantStatus,
    TenantAccessReconciliationStatus,
    TenantAccessScope,
    TenantCredential,
    TenantCredentialDeliveryMethod,
    TenantCredentialStatus,
    TenantCredentialType,
    TenantMembership,
    TenantMembershipPrincipalType,
    TenantMembershipStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)


@dataclass(frozen=True, slots=True)
class DeployerCredentialIssueRequest:
    application_name: str
    purpose: str = 'github-actions-helm'
    validity_days: int = DEFAULT_CREDENTIAL_VALIDITY_DAYS


def _deployer_service_account_name(*, application_name: str, environment: str, public_id: str) -> str:
    suffix = public_id.replace('-', '')[:8]
    base = f'kaori-deploy-{application_name[:24]}-{environment[:12]}-{suffix}'
    return base[:63].rstrip('-')


def _existing_deployer_identity(
    *,
    tenant_id: str,
    application_name: str,
    purpose: str,
) -> TenantCredential | None:
    return TenantCredential.query.filter_by(
        tenant_id=tenant_id,
        credential_type=TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT.value,
        application_name=application_name,
        purpose=purpose,
    ).first()


def create_deployer_credential_committed(
    *,
    tenant_namespace_id: int,
    owner_user_id: int,
    request: DeployerCredentialIssueRequest,
    actor: User | None = None,
) -> TenantCredential:
    namespace = db.session.get(TenantNamespace, tenant_namespace_id)
    owner = db.session.get(User, owner_user_id)
    if namespace is None:
        raise ValueError('Select a managed Tenant namespace.')
    if namespace.provisioning_status != TenantNamespaceProvisioningStatus.READY.value:
        raise ValueError('Deployer credential requires a Ready managed namespace.')
    if owner is None or not owner.is_active:
        raise ValueError('Select an active accountable credential owner.')

    tenant = db.session.get(Tenant, namespace.environment.tenant_id)
    if tenant is None:
        raise ValueError('Tenant namespace no longer has a Tenant.')
    application_name = normalize_deployer_application(request.application_name)
    environment = namespace.environment.environment
    purpose = normalize_credential_purpose(f'{request.purpose}-{application_name}-{environment}')
    if (
        _existing_deployer_identity(
            tenant_id=tenant.id,
            application_name=application_name,
            purpose=purpose,
        )
        is not None
    ):
        raise ValueError('This application already has a Tenant deployer credential for the selected environment.')

    started, renewal_due_at, valid_until = _validity_window(validity_days=request.validity_days)
    public_id = str(uuid.uuid4())
    service_account_name = _deployer_service_account_name(
        application_name=application_name,
        environment=environment,
        public_id=public_id,
    )
    profile = get_access_profile('deployer')

    membership = TenantMembership()
    membership.tenant = tenant
    membership.principal_type = TenantMembershipPrincipalType.SERVICE_ACCOUNT.value
    membership.subject_name = service_account_name
    membership.status = TenantMembershipStatus.ACTIVE.value

    grant = TenantAccessGrant()
    grant.tenant = tenant
    grant.membership = membership
    grant.namespace = namespace
    grant.scope_type = TenantAccessScope.NAMESPACE.value
    grant.access_profile = profile.key.value
    grant.access_profile_version = profile.version
    grant.status = TenantAccessGrantStatus.ACTIVE.value
    grant.reconciliation_status = TenantAccessReconciliationStatus.PENDING.value

    credential = TenantCredential()
    credential.public_id = public_id
    credential.tenant = tenant
    credential.owner_user = owner
    credential.access_grant = grant
    credential.credential_type = TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT.value
    credential.purpose = purpose
    credential.application_name = application_name
    credential.delivery_method = TenantCredentialDeliveryMethod.CICD_KUBECONFIG.value
    credential.status = TenantCredentialStatus.ACTIVE.value
    credential.service_account_name = service_account_name
    credential.valid_from = started
    credential.renewal_due_at = renewal_due_at
    credential.valid_until = valid_until
    credential.rotation_generation = 1
    db.session.add_all([membership, grant, credential])

    try:
        validate_active_grant(grant)
        validate_credential_contract(credential)
        db.session.flush()
        reconcile_native_access_grant(grant)
        reconcile_native_credential(credential)
        _record_generation(credential, issued_at=started)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.deployer_issued',
            summary='Tenant CI/CD Deployer credential entitlement was issued and reconciled.',
            outcome='success',
            extra={
                'access_grant_id': grant.public_id,
                'application_name': application_name,
                'environment': environment,
                'namespace': namespace.namespace,
            },
        )
        db.session.commit()
        return credential
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantCredentialStateConflictError(
            'Committed Tenant deployer credential state changed while this identity was being issued. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise
