from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.tenant import (
    TenantAccessScope,
    TenantCredentialStatus,
    TenantCredentialType,
    TenantProductionAccessExceptionStatus,
)

_MUTATING_VERBS = frozenset({'create', 'update', 'patch', 'delete', 'deletecollection'})


@dataclass(frozen=True, slots=True)
class ProductionAccessDecision:
    allowed: bool
    compliant: bool
    authority: str
    findings: tuple[str, ...]
    reason: str


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_production_namespace(namespace) -> bool:
    environment = getattr(getattr(namespace, 'environment', None), 'environment', None)
    return str(getattr(environment, 'value', environment) or '').lower() == 'production'


def effective_production_exception_status(exception, *, now: datetime | None = None) -> str:
    status = str(getattr(exception, 'status', '') or '')
    if status == TenantProductionAccessExceptionStatus.REVOKED.value:
        return status
    current = _aware(now or datetime.now(UTC))
    if current >= _aware(exception.valid_until):
        return TenantProductionAccessExceptionStatus.EXPIRED.value
    return TenantProductionAccessExceptionStatus.ACTIVE.value


def _active_exception_matches(exception, credential, namespace, *, now: datetime) -> bool:
    if exception is None:
        return False
    if effective_production_exception_status(exception, now=now) != TenantProductionAccessExceptionStatus.ACTIVE.value:
        return False
    return (
        exception.credential_id == credential.id
        if hasattr(exception, 'credential_id')
        else exception.access_grant_id == credential.access_grant.id
    ) and exception.tenant_namespace_id == namespace.id and exception.owner_user_id == credential.owner_user_id


def _validate_deployer(credential, namespace) -> None:
    grant = credential.access_grant
    if grant is None or grant.access_profile != 'deployer':
        raise ValueError('Production pipeline credential requires the Deployer Access Profile.')
    if grant.scope_type != TenantAccessScope.NAMESPACE.value or grant.namespace is None or grant.namespace.id != namespace.id:
        raise ValueError('Production Deployer credential must be bound to exactly one namespace.')
    if grant.membership.principal_type != 'service_account':
        raise ValueError('Production Deployer credential requires a ServiceAccount principal.')
    if grant.status != 'active':
        raise ValueError('Production Deployer Access Grant is not active.')
    if not (credential.application_name or '').strip():
        raise ValueError('Production Deployer credential requires an application identity.')


def evaluate_production_access(
    credential,
    namespace,
    *,
    verb: str,
    exception=None,
    now: datetime | None = None,
) -> ProductionAccessDecision:
    normalized_verb = verb.strip().lower()
    current = _aware(now or datetime.now(UTC))

    if not is_production_namespace(namespace):
        return ProductionAccessDecision(
            allowed=True,
            compliant=True,
            authority='standard',
            findings=(),
            reason='Non-production namespace uses the standard Tenant authorization path.',
        )

    if normalized_verb not in _MUTATING_VERBS:
        return ProductionAccessDecision(
            allowed=True,
            compliant=True,
            authority='read',
            findings=(),
            reason='Read-only production access remains governed by the existing Access Grant.',
        )

    if credential.status not in {
        TenantCredentialStatus.ACTIVE.value,
        TenantCredentialStatus.RENEWAL_DUE.value,
    }:
        return ProductionAccessDecision(
            allowed=False,
            compliant=False,
            authority='denied',
            findings=('production_direct_access_denied',),
            reason='Inactive Tenant credential cannot mutate a production namespace.',
        )

    credential_type = TenantCredentialType(credential.credential_type)
    if credential_type is TenantCredentialType.DEPLOYER_SERVICE_ACCOUNT:
        _validate_deployer(credential, namespace)
        return ProductionAccessDecision(
            allowed=True,
            compliant=True,
            authority='pipeline',
            findings=(),
            reason='Approved namespace-scoped Deployer credential is the production mutation authority.',
        )

    if credential_type is TenantCredentialType.ADMIN_KUBECONFIG:
        return ProductionAccessDecision(
            allowed=True,
            compliant=False,
            authority='administrator',
            findings=('production_direct_access', 'production_human_mutation'),
            reason='Administrator mutation is attributable but is not pipeline-compliant production delivery.',
        )

    if credential_type is TenantCredentialType.HUMAN_SERVICE_ACCOUNT:
        if _active_exception_matches(exception, credential, namespace, now=current):
            return ProductionAccessDecision(
                allowed=True,
                compliant=False,
                authority='exception',
                findings=(
                    'production_direct_access',
                    'production_human_mutation',
                    'production_exception_used',
                ),
                reason='Bounded governed exception permits this ordinary-human production mutation.',
            )
        return ProductionAccessDecision(
            allowed=False,
            compliant=False,
            authority='denied',
            findings=('production_direct_access_denied',),
            reason='Ordinary human production mutation requires an active governed exception.',
        )

    return ProductionAccessDecision(
        allowed=False,
        compliant=False,
        authority='denied',
        findings=('production_direct_access_denied',),
        reason='Unsupported production mutation identity fails closed.',
    )
