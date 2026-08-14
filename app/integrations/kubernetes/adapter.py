from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.compatibility import kubernetes_lifecycle_policy
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.kubernetes.messages import compact_readiness_reasons
from app.integrations.runtime.scoring import calculate_health
from app.models.kubernetes import KubernetesConnection


class KubernetesRuntimeAdapter:
    """Provider-neutral runtime adapter for canonical Kubernetes connections."""

    provider = 'kubernetes'

    @staticmethod
    def _cluster(instance: KubernetesConnection | Any):
        return instance.cluster if isinstance(instance, KubernetesConnection) else instance

    def refresh(self, instance: KubernetesConnection | Any):
        from app.cluster.service import run_test_cluster

        return run_test_cluster(self._cluster(instance))

    def refresh_health(self, instance: KubernetesConnection | Any):
        from app.cluster.service import refresh_cluster_runtime_health

        return refresh_cluster_runtime_health(self._cluster(instance))

    def build_client(self, instance: KubernetesConnection | Any):
        from app.integrations.kubernetes.client import KubernetesClient

        connection = instance if isinstance(instance, KubernetesConnection) else instance.kubernetes_connection
        if connection is None or not connection.kubeconfig:
            raise ValueError('The Kubernetes connection has no canonical kubeconfig credential.')
        return KubernetesClient(
            connection.kubeconfig,
            verify_ssl=bool(connection.verify_ssl),
        )

    def execute(self, operation: str, instance: KubernetesConnection | Any, **kwargs: Any):
        if operation == 'client.build':
            return self.build_client(instance)
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        if operation == 'inventory.sync':
            from app.inventory.kubernetes.synchronization import sync_inventory

            connection = instance if isinstance(instance, KubernetesConnection) else instance.kubernetes_connection
            if connection is None:
                raise ValueError('The Kubernetes integration has no canonical connection.')
            return sync_inventory(
                self._cluster(connection),
                connection,
                progress_callback=kwargs.get('progress_callback'),
            )
        raise ValueError(f'Unsupported Kubernetes integration operation: {operation}')

    def get_state(self, instance: KubernetesConnection | Any, *, validation_result=None) -> RuntimeState:
        connection = instance if isinstance(instance, KubernetesConnection) else instance.kubernetes_connection
        cluster = self._cluster(instance)
        now = datetime.now(UTC)
        connected = cluster.status == 'connected'
        readiness = getattr(connection, 'readiness_status', None) or ('ready' if connected else 'validation_required')
        discovery = connection.discovery_summary or {}
        validation_payload = validation_result if isinstance(validation_result, dict) else {}
        runtime_message = (
            validation_payload.get('validation_message')
            or validation_payload.get('message')
            or validation_payload.get('error')
            or ''
        )
        blocked = tuple(discovery.get('blocked_features') or ())
        legacy = tuple(discovery.get('legacy_features') or ())
        optional_blocked = tuple(discovery.get('optional_blocked_features') or ())
        lifecycle = str(discovery.get('lifecycle_status') or 'unknown')
        lifecycle_policy = kubernetes_lifecycle_policy(connection.detected_version)
        readiness_reasons = tuple(compact_readiness_reasons(discovery.get('readiness_reasons') or ()))
        selected_adapters = discovery.get('selected_adapters') or {}
        capabilities = tuple(sorted({key.split('.', 1)[0] for key in selected_adapters}))
        if connected:
            capabilities = tuple(sorted(set(capabilities) | {'inventory', 'operations', 'governance', 'discovery'}))

        factors = (
            HealthFactor(
                'connectivity',
                'Kubernetes API',
                'success' if connected else 'failed',
                50,
                100 if connected else 0,
                runtime_message,
            ),
            HealthFactor(
                'compatibility',
                'API compatibility and lifecycle',
                'success' if readiness == 'ready' else ('failed' if blocked else 'warning'),
                30,
                100 if readiness == 'ready' else (20 if blocked else 60),
                (
                    ' '.join(readiness_reasons)
                    or (
                        f'Kubernetes {connection.detected_version or "unknown"} lifecycle: {lifecycle}.'
                        if lifecycle != 'current'
                        else connection.compatibility_profile or ''
                    )
                ),
            ),
            HealthFactor(
                'capabilities',
                'Capability contract',
                'failed' if blocked else ('warning' if legacy else 'success'),
                20,
                20 if blocked else (70 if legacy else 100),
                f'{len(selected_adapters)} feature adapter(s) selected.',
            ),
        )
        diagnostics = [
            DiagnosticResult(
                'api',
                'Kubernetes API',
                'connectivity',
                'success' if connected else 'failed',
                runtime_message or ('API connected.' if connected else 'API unavailable.'),
                severity='critical' if not connected else 'info',
            ),
            DiagnosticResult(
                'lifecycle',
                'Version lifecycle',
                'compatibility',
                'warning' if lifecycle == 'legacy' else ('pending' if lifecycle == 'unknown' else 'success'),
                (
                    (' '.join(readiness_reasons) + ' ' if readiness_reasons else '')
                    + f'KAORI current lifecycle band: {lifecycle_policy["current_version_band"]}; '
                    + f'accepted compatibility contract: {lifecycle_policy["supported_constraint"]}.'
                ),
                severity='warning' if lifecycle == 'legacy' else 'info',
                recommendation=(
                    f'Plan an upgrade into the KAORI current lifecycle band {lifecycle_policy["current_version_band"]}, then rerun Full Validation.'
                    if lifecycle == 'legacy'
                    else None
                ),
            ),
            DiagnosticResult(
                'compatibility',
                'API compatibility',
                'compatibility',
                'failed' if blocked else ('warning' if legacy else ('success' if connected else 'pending')),
                (
                    f'{len(blocked)} blocked feature(s): {", ".join(blocked[:5])}'
                    if blocked
                    else f'{len(legacy)} feature(s) use tested legacy APIs.'
                    if legacy
                    else 'Stable API candidates are selected for discovered features.'
                ),
                severity='critical' if blocked else ('warning' if legacy else 'info'),
            ),
        ]
        return RuntimeState(
            provider=self.provider,
            instance_id=str(getattr(connection, 'id', cluster.id)),
            instance_name=getattr(getattr(connection, 'integration_instance', None), 'name', None) or cluster.name,
            observed_at=cluster.last_check or connection.last_validated_at or now,
            readiness=readiness,
            health=calculate_health(factors),
            diagnostics=tuple(diagnostics),
            snapshot=CapabilitySnapshot(
                profile=connection.compatibility_profile,
                compatibility_profile=connection.compatibility_profile,
                capabilities=capabilities,
                observed_at=cluster.last_check or connection.last_validated_at or now,
                metadata={
                    'version': connection.detected_version,
                    'platform': connection.detected_platform,
                    'lifecycle_status': lifecycle,
                    'lifecycle_policy': lifecycle_policy,
                    'readiness_reasons': list(readiness_reasons),
                    'blocked_features': list(blocked),
                    'legacy_features': list(legacy),
                    'optional_blocked_features': list(optional_blocked),
                    'selected_adapters': selected_adapters,
                },
            ),
            last_success_at=cluster.last_check if connected else None,
            last_failure_at=cluster.last_check if not connected else None,
            message=(
                ' '.join(readiness_reasons)
                or runtime_message
                or ('Kubernetes runtime is ready.' if connected else 'Kubernetes runtime requires attention.')
            ),
        )


runtime_adapter = KubernetesRuntimeAdapter()
