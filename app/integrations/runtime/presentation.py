from __future__ import annotations

from app.integrations.runtime.contracts import RuntimeState


def runtime_state_view(state: RuntimeState) -> dict[str, object]:
    return {
        'provider': state.provider,
        'instance_id': state.instance_id,
        'instance_name': state.instance_name,
        'observed_at': state.observed_at,
        'readiness': state.readiness,
        'health_status': state.health.status,
        'health_score': state.health.score,
        'health_summary': state.health.summary,
        'diagnostics': state.diagnostics,
        'factors': state.health.factors,
        'capability_profile': state.snapshot.profile,
        'compatibility_profile': state.snapshot.compatibility_profile,
        'capability_count': len(state.snapshot.capabilities),
        'capabilities': state.snapshot.capabilities,
        'latency_ms': state.latency_ms,
        'last_success_at': state.last_success_at,
        'last_failure_at': state.last_failure_at,
        'message': state.message,
    }
