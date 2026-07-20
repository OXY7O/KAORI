from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.runtime.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.models.integration import KubernetesConnection


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

    def get_state(self, instance: KubernetesConnection | Any, *, validation_result=None) -> RuntimeState:
        connection = instance if isinstance(instance, KubernetesConnection) else instance.kubernetes_connection
        cluster = self._cluster(instance)
        now = datetime.now(UTC)
        connected = cluster.status == 'connected'
        readiness = (
            getattr(connection, 'readiness_status', None)
            or cluster.kubernetes_readiness_status
            or ('ready' if connected else 'validation_required')
        )
        discovery = getattr(connection, 'discovery_summary', None) or cluster.kubernetes_api_discovery_summary or {}
        validation_payload = validation_result if isinstance(validation_result, dict) else {}
        runtime_message = (
            validation_payload.get('validation_message')
            or validation_payload.get('message')
            or validation_payload.get('error')
            or cluster.kubernetes_validation_message
            or ''
        )
        blocked = tuple(discovery.get('blocked_features') or ())
        legacy = tuple(discovery.get('legacy_features') or ())
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
                'API compatibility',
                'success' if readiness == 'ready' else ('failed' if blocked else 'warning'),
                30,
                100 if readiness == 'ready' else (20 if blocked else 60),
                getattr(connection, 'compatibility_profile', None) or cluster.kubernetes_compatibility_profile or '',
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
            observed_at=cluster.last_check or getattr(connection, 'last_validated_at', None) or cluster.kubernetes_last_validated_at or now,
            readiness=readiness,
            health=calculate_health(factors),
            diagnostics=tuple(diagnostics),
            snapshot=CapabilitySnapshot(
                profile=getattr(connection, 'compatibility_profile', None) or cluster.kubernetes_compatibility_profile,
                compatibility_profile=getattr(connection, 'compatibility_profile', None) or cluster.kubernetes_compatibility_profile,
                capabilities=capabilities,
                observed_at=cluster.last_check or getattr(connection, 'last_validated_at', None) or now,
                metadata={
                    'version': cluster.kubernetes_version,
                    'platform': cluster.kubernetes_platform,
                    'blocked_features': list(blocked),
                    'legacy_features': list(legacy),
                    'selected_adapters': selected_adapters,
                },
            ),
            last_success_at=cluster.last_check if connected else None,
            last_failure_at=cluster.last_check if not connected else None,
            message=runtime_message or ('Kubernetes runtime is ready.' if connected else 'Kubernetes runtime requires attention.'),
        )


runtime_adapter = KubernetesRuntimeAdapter()
