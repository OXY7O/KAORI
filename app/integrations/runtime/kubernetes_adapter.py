from __future__ import annotations

from datetime import UTC, datetime

from app.integrations.runtime.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.models import Cluster


class KubernetesRuntimeAdapter:
    """Runtime view of a Kubernetes API endpoint, independent of metrics and alerts."""

    provider = 'kubernetes'

    def refresh(self, instance: Cluster):
        from app.cluster.service import test_cluster_connection
        return test_cluster_connection(instance)

    def get_state(self, instance: Cluster, *, validation_result=None) -> RuntimeState:
        now = datetime.now(UTC)
        connected = instance.status == 'connected'
        readiness = instance.kubernetes_readiness_status or ('ready' if connected else 'validation_required')
        factors = (
            HealthFactor('connectivity', 'Kubernetes API', 'success' if connected else 'failed', 60, 100 if connected else 0, instance.kubernetes_validation_message or ''),
            HealthFactor('compatibility', 'API compatibility', 'success' if readiness == 'ready' else 'warning', 40, 100 if readiness == 'ready' else 50, instance.kubernetes_compatibility_profile or ''),
        )
        return RuntimeState(
            provider=self.provider,
            instance_id=instance.id,
            instance_name=instance.name,
            observed_at=instance.last_check or instance.kubernetes_last_validated_at or now,
            readiness=readiness,
            health=calculate_health(factors),
            diagnostics=(DiagnosticResult('api', 'Kubernetes API', 'connectivity', 'success' if connected else 'failed', instance.kubernetes_validation_message or ('API connected.' if connected else 'API unavailable.'), severity='critical' if not connected else 'info'),),
            snapshot=CapabilitySnapshot(
                profile=instance.kubernetes_compatibility_profile,
                compatibility_profile=instance.kubernetes_compatibility_profile,
                capabilities=('inventory', 'operations') if connected else (),
                observed_at=instance.last_check or instance.kubernetes_last_validated_at or now,
                metadata={'version': instance.kubernetes_version, 'platform': instance.kubernetes_platform},
            ),
            last_success_at=instance.last_check if connected else None,
            last_failure_at=instance.last_check if not connected else None,
            message=instance.kubernetes_validation_message or ('Kubernetes runtime is ready.' if connected else 'Kubernetes runtime requires attention.'),
        )


runtime_adapter = KubernetesRuntimeAdapter()
