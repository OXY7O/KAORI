from __future__ import annotations

from app.common.presentation import present_count, present_key_label, present_milliseconds, present_user_datetime
from app.integrations.runtime.contracts import RuntimeState


def runtime_state_view(state: RuntimeState) -> dict[str, object]:
    return {
        'provider': state.provider,
        'instance_id': state.instance_id,
        'instance_name': state.instance_name,
        'observed_at': state.observed_at,
        'readiness': state.readiness,
        'readiness_label': present_key_label(state.readiness),
        'health_status': state.health.status,
        'health_status_label': present_key_label(state.health.status),
        'health_score': state.health.score,
        'health_summary': state.health.summary,
        'diagnostics': state.diagnostics,
        'factors': state.health.factors,
        'capability_profile': state.snapshot.profile,
        'compatibility_profile': state.snapshot.compatibility_profile,
        'capability_count': len(state.snapshot.capabilities),
        'capability_count_display': present_count(len(state.snapshot.capabilities), 'capability'),
        'capabilities': state.snapshot.capabilities,
        'latency_ms': state.latency_ms,
        'latency_display': present_milliseconds(state.latency_ms),
        'last_success_at': state.last_success_at,
        'last_failure_at': state.last_failure_at,
        'message': state.message,
        'health_score_display': f'{state.health.score}/100',
        'observed_at_display': present_user_datetime(state.observed_at, empty='Not observed', include_seconds=True),
    }


def runtime_history_view(rows, *, pagination: dict[str, object]) -> dict[str, object]:
    per_page = int(pagination.get('per_page', 5))
    rendered_source_rows = rows[:per_page]
    chronological = list(reversed(rows))
    previous_by_id: dict[int, object | None] = {}
    previous = None
    for row in chronological:
        previous_by_id[row.id] = previous
        previous = row

    rendered_rows = []
    for row in rendered_source_rows:
        previous_row = previous_by_id.get(row.id)
        current_capabilities = set((row.capability_snapshot or {}).get('capabilities') or [])
        previous_capabilities = set(
            ((previous_row.capability_snapshot or {}).get('capabilities') or [])
            if previous_row is not None
            else []
        )
        added_capabilities = (
            sorted(current_capabilities - previous_capabilities)
            if previous_row is not None
            else []
        )
        removed_capabilities = (
            sorted(previous_capabilities - current_capabilities)
            if previous_row is not None
            else []
        )
        transition = _runtime_transition(row, previous_row)
        rendered_rows.append({
            'id': row.id,
            'observed_at': row.observed_at,
            'observed_at_display': present_user_datetime(row.observed_at, empty='Unknown', include_seconds=True),
            'trigger_type': row.trigger_type,
            'trigger_type_label': present_key_label(row.trigger_type),
            'readiness': row.readiness,
            'readiness_label': present_key_label(row.readiness),
            'health_status': row.health_status,
            'health_status_label': present_key_label(row.health_status),
            'health_score': row.health_score,
            'health_score_display': f'{row.health_score}/100',
            'latency_ms': row.latency_ms,
            'latency_display': present_milliseconds(row.latency_ms),
            'compatibility_profile': row.compatibility_profile,
            'capability_profile': row.capability_profile,
            'capability_count': len(current_capabilities),
            'capability_count_display': present_count(len(current_capabilities), 'observed capability'),
            'transition': transition,
            'added_capabilities': added_capabilities,
            'removed_capabilities': removed_capabilities,
            'capability_changed': bool(added_capabilities or removed_capabilities),
            'message': row.message,
        })

    health_counts = {'healthy': 0, 'degraded': 0, 'unhealthy': 0}
    for row in rendered_source_rows:
        if row.health_status in health_counts:
            health_counts[row.health_status] += 1

    latest = rendered_source_rows[0] if rendered_source_rows else None
    return {
        'rows': rendered_rows,
        'pagination': pagination,
        'latest_status': latest.health_status if latest else 'not_observed',
        'latest_score': latest.health_score if latest else None,
        'health_counts': health_counts,
    }


def _runtime_transition(row, previous_row) -> dict[str, str] | None:
    if previous_row is None or previous_row.health_status == row.health_status:
        return None
    current = row.health_status
    previous = previous_row.health_status
    if current == 'healthy' and previous in {'degraded', 'unhealthy'}:
        return {'kind': 'recovered', 'label': 'Recovered'}
    if current == 'unhealthy' and previous != 'unhealthy':
        return {'kind': 'failed', 'label': 'Became unhealthy'}
    if current == 'degraded' and previous == 'healthy':
        return {'kind': 'degraded', 'label': 'Degraded'}
    if current == 'degraded' and previous == 'unhealthy':
        return {'kind': 'improving', 'label': 'Improving'}
    return {'kind': 'changed', 'label': f'{previous.replace("_", " ").title()} → {current.replace("_", " ").title()}'}
