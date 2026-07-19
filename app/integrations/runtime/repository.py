from __future__ import annotations

from math import ceil

from app.extensions.db import db
from app.models.integration_runtime import IntegrationRuntimeObservation

from .contracts import RuntimeState

MAX_RUNTIME_OBSERVATIONS_PER_INSTANCE = 100


def persist_runtime_state(
    state: RuntimeState,
    *,
    trigger_type: str,
    integration_instance_id: int | None = None,
) -> IntegrationRuntimeObservation:
    row = IntegrationRuntimeObservation(
        integration_instance_id=integration_instance_id,
        provider=state.provider,
        instance_id=state.instance_id,
        instance_name=state.instance_name,
        trigger_type=trigger_type,
        readiness=state.readiness,
        health_status=state.health.status,
        health_score=state.health.score,
        latency_ms=state.latency_ms,
        compatibility_profile=state.snapshot.compatibility_profile,
        capability_profile=state.snapshot.profile,
        capability_snapshot={
            'capabilities': list(state.snapshot.capabilities),
            'metadata': state.snapshot.metadata,
        },
        diagnostics=[
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
        ],
        message=state.message,
        observed_at=state.observed_at,
    )
    db.session.add(row)
    db.session.flush()
    prune_runtime_history(
        state.provider,
        state.instance_id,
        keep=MAX_RUNTIME_OBSERVATIONS_PER_INSTANCE,
    )
    db.session.commit()
    return row


def prune_runtime_history(
    provider: str,
    instance_id: str,
    *,
    keep: int = MAX_RUNTIME_OBSERVATIONS_PER_INSTANCE,
) -> int:
    """Delete runtime observations beyond the rolling per-instance retention limit.

    Retention is scoped by provider and provider-native instance ID so legacy rows
    without a canonical integration_instance_id are pruned consistently as well.
    The caller owns the transaction; persist_runtime_state commits the insert and
    pruning operation together.
    """
    keep = max(int(keep), 1)
    stale_ids = [
        row_id
        for (row_id,) in (
            IntegrationRuntimeObservation.query.with_entities(
                IntegrationRuntimeObservation.id,
            )
            .filter(
                IntegrationRuntimeObservation.provider == provider,
                IntegrationRuntimeObservation.instance_id == str(instance_id),
            )
            .order_by(
                IntegrationRuntimeObservation.observed_at.desc(),
                IntegrationRuntimeObservation.id.desc(),
            )
            .offset(keep)
            .all()
        )
    ]
    if not stale_ids:
        return 0

    deleted = (
        IntegrationRuntimeObservation.query.filter(
            IntegrationRuntimeObservation.id.in_(stale_ids),
        )
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


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
) -> tuple[list[IntegrationRuntimeObservation], dict[str, object]]:
    allowed_per_page = (5, 10, 25, 50)
    if per_page not in allowed_per_page:
        per_page = 5

    query = IntegrationRuntimeObservation.query.filter_by(
        provider=provider,
        instance_id=str(instance_id),
    )
    total_items = query.count()
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(max(page, 1), total_pages)
    rows = (
        query.order_by(
            IntegrationRuntimeObservation.observed_at.desc(),
            IntegrationRuntimeObservation.id.desc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page + 1)
        .all()
    )
    start_item = ((page - 1) * per_page) + 1 if total_items else 0
    return rows, {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_item,
        'end_item': min(page * per_page, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed_per_page,
        'retention_limit': MAX_RUNTIME_OBSERVATIONS_PER_INSTANCE,
    }
