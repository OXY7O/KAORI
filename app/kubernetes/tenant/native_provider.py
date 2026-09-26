from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.extensions.db import db
from app.kubernetes.tenant.access_reconciliation import reconcile_native_access_grant
from app.kubernetes.tenant.credential_reconciliation import reconcile_native_credential
from app.kubernetes.tenant.managed_resources import reconcile_native_managed_resource
from app.kubernetes.tenant.provisioning import reconcile_native_namespace
from app.kubernetes.tenant.providers import (
    TenantCapabilityStatus,
    TenantProviderCapability,
    TenantProviderError,
    TenantProviderKey,
    TenantProviderOperationResult,
    TenantProviderResult,
    TenantProviderState,
)
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import Tenant
from app.models.tenant_managed_resource import TenantManagedResourceKind

_BASELINE_FEATURES: dict[str, tuple[str, ...]] = {
    'namespace': ('tenant.namespaces',),
    'resource_quota': ('tenant.resourcequotas',),
    'limit_range': ('tenant.limitranges',),
    'namespaced_rbac': ('tenant.rbac.roles', 'tenant.rbac.rolebindings'),
    'service_account_token': ('tenant.serviceaccounts', 'tenant.serviceaccount_tokens'),
    'managed_tls': ('tenant.secrets',),
    'managed_registry': ('tenant.secrets',),
}
_ADMISSION_FEATURES = (
    'tenant.admission.validatingpolicies',
    'tenant.admission.validatingpolicybindings',
)


def _feature_status(feature: dict[str, Any] | None) -> TenantCapabilityStatus:
    if not feature:
        return TenantCapabilityStatus.UNAVAILABLE
    status = str(feature.get('status') or '')
    if status == 'ready':
        return TenantCapabilityStatus.AVAILABLE
    if status == 'legacy':
        return TenantCapabilityStatus.DEGRADED
    return TenantCapabilityStatus.UNAVAILABLE


def _combine_status(statuses: list[TenantCapabilityStatus]) -> TenantCapabilityStatus:
    if TenantCapabilityStatus.UNAVAILABLE in statuses:
        return TenantCapabilityStatus.UNAVAILABLE
    if TenantCapabilityStatus.DEGRADED in statuses:
        return TenantCapabilityStatus.DEGRADED
    return TenantCapabilityStatus.AVAILABLE


class NativeKubernetesTenantProvider:
    provider_key = TenantProviderKey.NATIVE_KUBERNETES

    def __init__(self, *, connection: KubernetesConnection | Any | None = None) -> None:
        self._connection = connection

    def _connection_for(self, cluster_id: str):
        if self._connection is not None:
            return self._connection
        connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()
        if connection is None:
            raise TenantProviderError(
                'connection_unavailable',
                'No canonical Kubernetes connection is bound to the selected cluster.',
            )
        return connection

    def capabilities(self, *, cluster_id: str) -> tuple[TenantProviderCapability, ...]:
        connection = self._connection_for(cluster_id)
        readiness = str(getattr(connection, 'readiness_status', None) or 'validation_required')
        discovery = getattr(connection, 'discovery_summary', None) or {}
        features = discovery.get('features') or {}

        if readiness != 'ready':
            status = (
                TenantCapabilityStatus.DEGRADED
                if readiness == 'degraded'
                else TenantCapabilityStatus.UNAVAILABLE
            )
            baseline = [
                TenantProviderCapability(
                    key=key,
                    status=status,
                    message='Canonical Kubernetes connection must pass Full Validation for Native Tenant mutations.',
                )
                for key in _BASELINE_FEATURES
            ]
            baseline.extend(
                (
                    TenantProviderCapability(
                        key='domain_policy_preflight',
                        status=status,
                        message='Tenant policy preflight is degraded while provider readiness is not Ready.',
                    ),
                    TenantProviderCapability(
                        key='service_exposure_preflight',
                        status=status,
                        message='Tenant exposure preflight is degraded while provider readiness is not Ready.',
                    ),
                    TenantProviderCapability(
                        key='admission_enforcement',
                        status=status,
                        message='Admission enforcement is unavailable until provider readiness is Ready.',
                    ),
                    TenantProviderCapability(
                        key='external_registry_provider',
                        status=TenantCapabilityStatus.NOT_APPLICABLE,
                        message='Native baseline does not assume a node credential-provider integration.',
                    ),
                )
            )
            return tuple(baseline)

        result: list[TenantProviderCapability] = []
        for capability, keys in _BASELINE_FEATURES.items():
            statuses = [_feature_status(features.get(key)) for key in keys]
            result.append(
                TenantProviderCapability(
                    key=capability,
                    status=_combine_status(statuses),
                    message='; '.join(
                        str((features.get(key) or {}).get('message') or f'{key} evidence unavailable')
                        for key in keys
                    ),
                )
            )

        result.extend(
            (
                TenantProviderCapability(
                    key='domain_policy_preflight',
                    status=TenantCapabilityStatus.AVAILABLE,
                    message='KAORI committed hostname ownership preflight is available.',
                ),
                TenantProviderCapability(
                    key='service_exposure_preflight',
                    status=TenantCapabilityStatus.AVAILABLE,
                    message='KAORI committed Service/Ingress exposure preflight is available.',
                ),
                TenantProviderCapability(
                    key='admission_enforcement',
                    status=_combine_status([_feature_status(features.get(key)) for key in _ADMISSION_FEATURES]),
                    message='; '.join(
                        str((features.get(key) or {}).get('message') or f'{key} evidence unavailable')
                        for key in _ADMISSION_FEATURES
                    ),
                ),
                TenantProviderCapability(
                    key='external_registry_provider',
                    status=TenantCapabilityStatus.NOT_APPLICABLE,
                    message='Native baseline uses managed image-pull Secret unless a stronger provider is integrated.',
                ),
            )
        )
        return tuple(result)

    def validate_binding(self, *, cluster_id: str) -> TenantProviderResult:
        capabilities = self.capabilities(cluster_id=cluster_id)
        return TenantProviderResult(
            provider_key=self.provider_key,
            state=TenantProviderState.NATIVE,
            capabilities=capabilities,
            evidence_reference=f'kubernetes-connection:{cluster_id}',
        )

    @staticmethod
    def validate_tenant_authority(tenant: Tenant | Any) -> None:
        if (
            tenant.provider_key != TenantProviderKey.NATIVE_KUBERNETES.value
            or tenant.provider_state != TenantProviderState.NATIVE.value
        ):
            raise ValueError('Native Kubernetes authority is required for this Tenant operation.')

    def commit_provider_evidence(self, tenant: Tenant, *, commit: bool = False) -> dict[str, object]:
        self.validate_tenant_authority(tenant)
        capabilities = self.capabilities(cluster_id=tenant.cluster_id)
        evidence = {
            'provider': self.provider_key.value,
            'provider_state': tenant.provider_state,
            'capabilities': [asdict(item) for item in capabilities],
            'secret_material_persisted': False,
        }
        tenant.provider_evidence_json = evidence
        if commit:
            db.session.commit()
        return evidence

    def operation_result(
        self,
        *,
        operation: str,
        capability: str,
        status: str,
        desired_hash: str | None = None,
        effective_hash: str | None = None,
        evidence: dict[str, object] | None = None,
        message: str = '',
        error_code: str | None = None,
    ) -> TenantProviderOperationResult:
        return TenantProviderOperationResult(
            provider_key=self.provider_key,
            operation=operation,
            capability=capability,
            status=status,
            desired_hash=desired_hash,
            effective_hash=effective_hash,
            evidence=evidence,
            message=message,
            error_code=error_code,
        )

    def reconcile_namespace(self, record) -> TenantProviderOperationResult:
        self.validate_tenant_authority(record.environment.tenant)
        for capability in ('namespace', 'resource_quota', 'limit_range'):
            require_native_capability(self, cluster_id=record.cluster_id, capability=capability)
        reconcile_native_namespace(record)
        return self.operation_result(
            operation='namespace.reconcile',
            capability='namespace',
            status=record.provisioning_status,
            desired_hash=record.desired_hash,
            effective_hash=record.effective_hash,
            evidence={'namespace': record.namespace, 'secret_material_persisted': False},
            message=record.provisioning_message or '',
        )

    def reconcile_access_grant(self, grant) -> TenantProviderOperationResult:
        self.validate_tenant_authority(grant.tenant)
        require_native_capability(self, cluster_id=grant.tenant.cluster_id, capability='namespaced_rbac')
        reconcile_native_access_grant(grant)
        return self.operation_result(
            operation='access_grant.reconcile',
            capability='namespaced_rbac',
            status=grant.reconciliation_status,
            desired_hash=grant.desired_hash,
            effective_hash=grant.effective_hash,
            evidence={'access_grant_id': grant.public_id, 'secret_material_persisted': False},
            message=grant.reconciliation_message or '',
        )

    def reconcile_credential(self, credential) -> TenantProviderOperationResult:
        self.validate_tenant_authority(credential.tenant)
        require_native_capability(
            self,
            cluster_id=credential.tenant.cluster_id,
            capability='service_account_token',
        )
        reconcile_native_credential(credential)
        return self.operation_result(
            operation='credential.reconcile',
            capability='service_account_token',
            status=credential.reconciliation_status,
            desired_hash=credential.desired_hash,
            effective_hash=credential.effective_hash,
            evidence={'credential_id': credential.public_id, 'secret_material_persisted': False},
            message=credential.reconciliation_message or '',
        )

    def reconcile_managed_resource(self, intent, *, material=None, external_provider_ready: bool = False):
        self.validate_tenant_authority(intent.namespace.environment.tenant)
        capability = (
            'managed_tls'
            if intent.resource_kind == TenantManagedResourceKind.TLS.value
            else 'managed_registry'
        )
        require_native_capability(
            self,
            cluster_id=intent.namespace.cluster_id,
            capability=capability,
        )
        reconcile_native_managed_resource(
            intent,
            material=material,
            external_provider_ready=external_provider_ready,
        )
        return self.operation_result(
            operation='managed_resource.reconcile',
            capability=capability,
            status=intent.status,
            desired_hash=intent.desired_hash,
            effective_hash=intent.effective_hash,
            evidence={
                'managed_resource_id': intent.public_id,
                'resource_kind': intent.resource_kind,
                'secret_material_persisted': False,
            },
            message=intent.reconciliation_message or '',
        )


def require_native_capability(
    provider: NativeKubernetesTenantProvider,
    *,
    cluster_id: str,
    capability: str,
) -> TenantProviderCapability:
    selected = next(
        (item for item in provider.capabilities(cluster_id=cluster_id) if item.key == capability),
        None,
    )
    if selected is None or selected.status is not TenantCapabilityStatus.AVAILABLE:
        status = selected.status.value if selected is not None else 'unknown'
        raise TenantProviderError(
            'capability_unavailable',
            f'Native Tenant capability {capability} is {status}; security-sensitive operation fails closed.',
            capability=capability,
        )
    return selected
