from __future__ import annotations

from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window
from app.extensions.db import db
from app.integrations.contracts import RuntimeState
from app.models.runtime import IntegrationRuntimeObservation


def persist_runtime_state(
    state: RuntimeState,
    *,
    trigger_type: str,
    integration_instance_id: int | None = None,
) -> IntegrationRuntimeObservation:
    row = IntegrationRuntimeObservation()
    row.integration_instance_id = integration_instance_id
    row.provider = state.provider
    row.instance_id = state.instance_id
    row.instance_name = state.instance_name
    row.trigger_type = trigger_type
    row.readiness = state.readiness
    row.health_status = state.health.status
    row.health_score = state.health.score
    row.latency_ms = state.latency_ms
    row.compatibility_profile = state.snapshot.compatibility_profile
    row.capability_profile = state.snapshot.profile
    row.capability_snapshot = {
        'capabilities': list(state.snapshot.capabilities),
        'metadata': state.snapshot.metadata,
    }
    row.diagnostics = [
        {
            'key': diagnostic.key,
            'label': diagnostic.label,
            'category': diagnostic.category,
            'status': diagnostic.status,
            'detail': diagnostic.detail,
            'duration_ms': diagnostic.duration_ms,
            'severity': diagnostic.severity,
            'recommendation': diagnostic.recommendation,
        }
        for diagnostic in state.diagnostics
    ]
    row.message = state.message
    row.observed_at = state.observed_at
    db.session.add(row)
    db.session.flush()
    db.session.commit()
    return row


def list_runtime_history(
    provider: str,
    instance_id: str,
    *,
    limit: int = 5,
) -> list[IntegrationRuntimeObservation]:
    return (
        IntegrationRuntimeObservation.query.filter_by(
            provider=provider,
            instance_id=str(instance_id),
        )
        .order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .limit(limit)
        .all()
    )


def paginate_runtime_history(
    provider: str,
    instance_id: str,
    *,
    page: int = 1,
    per_page: int = 5,
    trigger_type: str = '',
    health_status: str = '',
    readiness: str = '',
) -> tuple[list[IntegrationRuntimeObservation], dict[str, object]]:
    trigger_filter = _normalized_filter(trigger_type, {'manual', 'scheduled', 'recovery'})
    health_filter = _normalized_filter(health_status, {'healthy', 'degraded', 'unhealthy'})
    readiness_filter = _normalized_filter(
        readiness,
        {'ready', 'degraded', 'validation_required', 'blocked'},
    )

    query = IntegrationRuntimeObservation.query.filter_by(
        provider=provider,
        instance_id=str(instance_id),
    )
    if trigger_filter:
        query = query.filter(IntegrationRuntimeObservation.trigger_type == trigger_filter)
    if health_filter:
        query = query.filter(IntegrationRuntimeObservation.health_status == health_filter)
    if readiness_filter:
        query = query.filter(IntegrationRuntimeObservation.readiness == readiness_filter)

    window = build_pagination_window(
        total_items=query.count(),
        page=page,
        per_page=per_page,
        allowed_per_page=PER_PAGE_OPTIONS,
    )
    rows = (
        query.order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .offset(window.offset)
        .limit(window.per_page)
        .all()
    )
    return rows, {
        **window.as_dict(),
        'allowed_per_page': PER_PAGE_OPTIONS,
        'filters': {
            'trigger_type': trigger_filter,
            'health_status': health_filter,
            'readiness': readiness_filter,
        },
    }


def _normalized_filter(value: object, allowed: set[str]) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in allowed else ''
