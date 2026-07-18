from __future__ import annotations
from app.extensions.db import db
from app.models.integration_runtime import IntegrationRuntimeObservation
from .contracts import RuntimeState

def persist_runtime_state(state: RuntimeState, *, trigger_type: str) -> IntegrationRuntimeObservation:
    row = IntegrationRuntimeObservation(
        provider=state.provider, instance_id=state.instance_id, instance_name=state.instance_name,
        trigger_type=trigger_type, readiness=state.readiness, health_status=state.health.status,
        health_score=state.health.score, latency_ms=state.latency_ms,
        compatibility_profile=state.snapshot.compatibility_profile,
        capability_profile=state.snapshot.profile,
        capability_snapshot={'capabilities': list(state.snapshot.capabilities), 'metadata': state.snapshot.metadata},
        diagnostics=[{'key': d.key, 'label': d.label, 'category': d.category, 'status': d.status, 'detail': d.detail, 'duration_ms': d.duration_ms, 'severity': d.severity, 'recommendation': d.recommendation} for d in state.diagnostics],
        message=state.message, observed_at=state.observed_at,
    )
    db.session.add(row)
    db.session.commit()
    return row

def list_runtime_history(provider: str, instance_id: str, *, limit: int = 5):
    return (IntegrationRuntimeObservation.query.filter_by(provider=provider, instance_id=str(instance_id))
            .order_by(IntegrationRuntimeObservation.observed_at.desc(), IntegrationRuntimeObservation.id.desc())
            .limit(limit).all())
