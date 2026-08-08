from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.common.presentation import present_count, present_key_label, present_milliseconds, present_user_datetime
from app.integrations.compatibility import kubernetes_lifecycle_policy
from app.integrations.contracts import RuntimeState
from app.models.runtime import IntegrationRuntimeObservation


def runtime_state_view(
    state: RuntimeState,
    *,
    actions: dict[str, str] | None = None,
    binding: dict[str, str] | None = None,
) -> dict[str, object]:
    actions = actions or {}
    binding = binding or {}
    metadata = state.snapshot.metadata or {}
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
        'diagnostics': [
            {
                'key': diagnostic.key,
                'label': diagnostic.label,
                'category': diagnostic.category,
                'category_label': present_key_label(diagnostic.category or 'runtime'),
                'status': diagnostic.status,
                'status_label': present_key_label(diagnostic.status),
                'detail': diagnostic.detail,
                'summary': _diagnostic_summary(diagnostic.detail, label=diagnostic.label),
                'duration_ms': diagnostic.duration_ms,
                'duration_display': present_milliseconds(diagnostic.duration_ms),
                'severity': diagnostic.severity,
                'recommendation': diagnostic.recommendation or '',
            }
            for diagnostic in state.diagnostics
        ],
        'factors': state.health.factors,
        'attention_factors': [
            {
                'key': factor.key,
                'label': factor.label,
                'status': factor.status,
                'score': factor.score,
                'detail': factor.detail,
            }
            for factor in state.health.factors
            if factor.status in {'warning', 'failed', 'unknown'} or factor.score < 85
        ],
        'capability_profile': state.snapshot.profile,
        'compatibility_profile': state.snapshot.compatibility_profile,
        'capability_count': len(state.snapshot.capabilities),
        'capability_count_display': present_count(len(state.snapshot.capabilities), 'capability'),
        'capabilities': state.snapshot.capabilities,
        'capability_metadata': metadata,
        'lifecycle_context': _kubernetes_lifecycle_context(state.provider, metadata),
        'latency_ms': state.latency_ms,
        'latency_display': present_milliseconds(state.latency_ms),
        'last_success_at': state.last_success_at,
        'last_failure_at': state.last_failure_at,
        'message': state.message,
        'health_score_display': f'{state.health.score}/100',
        'observed_at_display': present_user_datetime(state.observed_at, empty='Not observed', include_seconds=True),
        'refresh_url': actions.get('refresh_url'),
        'configuration_url': actions.get('configuration_url'),
        'history_url': actions.get('history_url'),
        'binding_type': binding.get('type'),
        'binding_id': binding.get('id'),
        'binding_name': binding.get('name'),
        'binding_label': binding.get('label'),
    }


def runtime_observation_state_view(
    observation: IntegrationRuntimeObservation | None,
    *,
    fallback_readiness: str = 'validation_required',
    fallback_compatibility_profile: str | None = None,
    fallback_capabilities: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Present persisted runtime evidence without inferring health from connection state.

    Fallback values may describe validation/readiness context, but runtime health, score,
    observation time, latency, diagnostics, and message are populated only from an
    actual persisted runtime observation.
    """
    fallback_capabilities = tuple(fallback_capabilities or ())
    if observation is None:
        readiness = fallback_readiness or 'validation_required'
        return {
            'has_observation': False,
            'readiness': readiness,
            'readiness_label': present_key_label(readiness),
            'health_status': 'not_observed',
            'health_status_label': 'Not Observed',
            'health_score': None,
            'health_score_display': 'N/A',
            'compatibility_profile': fallback_compatibility_profile,
            'capability_count': len(fallback_capabilities),
            'capability_count_display': present_count(len(fallback_capabilities), 'validated feature'),
            'capabilities': fallback_capabilities,
            'capability_metadata': {},
            'diagnostics': [],
            'factors': [],
            'attention_factors': [],
            'lifecycle_context': None,
            'observed_at': None,
            'observed_at_display': 'Never',
            'message': 'No persisted Kubernetes runtime observation is available yet.',
            'summary': 'No persisted Kubernetes runtime observation is available yet.',
            'latency_ms': None,
            'latency_display': 'N/A',
        }

    snapshot = observation.capability_snapshot or {}
    metadata = snapshot.get('metadata') or {}
    capabilities = tuple(snapshot.get('capabilities') or fallback_capabilities)
    diagnostics = _diagnostic_rows(observation.diagnostics or [])
    attention_factors = [
        {
            'key': item['key'],
            'label': item['label'],
            'status': item['status'],
            'score': 0 if item['status'] == 'failed' else 70,
            'detail': item['detail'],
        }
        for item in diagnostics
        if item['status'] in {'warning', 'failed', 'pending', 'unknown'}
    ]
    readiness = observation.readiness or fallback_readiness or 'validation_required'
    health_status = observation.health_status or 'not_observed'
    return {
        'has_observation': True,
        'readiness': readiness,
        'readiness_label': present_key_label(readiness),
        'health_status': health_status,
        'health_status_label': present_key_label(health_status),
        'health_score': observation.health_score,
        'health_score_display': (
            f'{observation.health_score}/100' if observation.health_score is not None else 'N/A'
        ),
        'compatibility_profile': observation.compatibility_profile or fallback_compatibility_profile,
        'capability_count': len(capabilities),
        'capability_count_display': present_count(len(capabilities), 'observed capability'),
        'capabilities': capabilities,
        'capability_metadata': metadata,
        'diagnostics': diagnostics,
        'factors': attention_factors,
        'attention_factors': attention_factors,
        'lifecycle_context': _kubernetes_lifecycle_context(observation.provider, metadata),
        'observed_at': observation.observed_at,
        'observed_at_display': present_user_datetime(
            observation.observed_at, empty='Not observed', include_seconds=True
        ),
        'message': observation.message or '',
        'summary': _runtime_primary_summary(
            provider=observation.provider,
            message=observation.message or '',
            diagnostics=diagnostics,
        ),
        'latency_ms': observation.latency_ms,
        'latency_display': present_milliseconds(observation.latency_ms),
    }


def runtime_history_view(
    rows: list[IntegrationRuntimeObservation],
    *,
    pagination: dict[str, object],
) -> dict[str, object]:
    per_page = _safe_int(pagination.get('per_page'), default=5)
    rendered_source_rows = rows[:per_page]
    chronological = list(reversed(rows))
    previous_by_id: dict[int, IntegrationRuntimeObservation | None] = {}
    previous: IntegrationRuntimeObservation | None = None
    for row in chronological:
        previous_by_id[row.id] = previous
        previous = row

    rendered_rows = []
    for row in rendered_source_rows:
        previous_row = previous_by_id.get(row.id)
        snapshot = row.capability_snapshot or {}
        metadata = snapshot.get('metadata') or {}
        current_capabilities = set(snapshot.get('capabilities') or [])
        previous_capabilities = set(
            ((previous_row.capability_snapshot or {}).get('capabilities') or []) if previous_row is not None else []
        )
        added_capabilities = sorted(current_capabilities - previous_capabilities) if previous_row is not None else []
        removed_capabilities = sorted(previous_capabilities - current_capabilities) if previous_row is not None else []
        transition = _runtime_transition(row, previous_row)
        diagnostics = _diagnostic_rows(row.diagnostics or [])
        lifecycle_context = _kubernetes_lifecycle_context(row.provider, metadata)
        effective_status = _effective_runtime_posture(row.health_status, row.readiness)
        rendered_rows.append(
            {
                'id': row.id,
                'detail_id': f'runtime-observation-{row.id}',
                'observed_at': row.observed_at,
                'observed_at_display': present_user_datetime(row.observed_at, empty='Unknown', include_seconds=True),
                'trigger_type': row.trigger_type,
                'trigger_type_label': present_key_label(row.trigger_type),
                'readiness': row.readiness,
                'readiness_label': present_key_label(row.readiness),
                'health_status': row.health_status,
                'health_status_label': present_key_label(row.health_status),
                'effective_status': effective_status,
                'effective_status_label': present_key_label(effective_status),
                'health_score': row.health_score,
                'health_score_display': f'{row.health_score}/100',
                'latency_ms': row.latency_ms,
                'latency_display': present_milliseconds(row.latency_ms),
                'compatibility_profile': row.compatibility_profile,
                'capability_profile': row.capability_profile,
                'capability_count': len(current_capabilities),
                'capability_count_display': present_count(len(current_capabilities), 'observed capability'),
                'capabilities': [
                    {'key': capability, 'label': present_key_label(capability)}
                    for capability in sorted(current_capabilities)
                ],
                'transition': transition,
                'added_capabilities': [present_key_label(value) for value in added_capabilities],
                'removed_capabilities': [present_key_label(value) for value in removed_capabilities],
                'capability_changed': bool(added_capabilities or removed_capabilities),
                'message': row.message,
                'message_redundant': _message_repeats_diagnostic(row.message or '', diagnostics),
                'standalone_message': (
                    row.message
                    if row.message and not _message_repeats_diagnostic(row.message or '', diagnostics)
                    else None
                ),
                'diagnostics': diagnostics,
                'diagnostic_count': len(diagnostics),
                'lifecycle_context': lifecycle_context,
                'has_detail': bool(row.message or diagnostics or current_capabilities or lifecycle_context),
            }
        )

    health_counts = {'healthy': 0, 'degraded': 0, 'unhealthy': 0}
    posture_counts = {'ready': 0, 'attention': 0, 'blocked': 0, 'not_observed': 0}
    for row in rendered_source_rows:
        if row.health_status in health_counts:
            health_counts[row.health_status] += 1
        posture = _effective_runtime_posture(row.health_status, row.readiness)
        if posture == 'ready':
            posture_counts['ready'] += 1
        elif posture == 'blocked':
            posture_counts['blocked'] += 1
        elif posture in {'degraded', 'validation_required'}:
            posture_counts['attention'] += 1
        else:
            posture_counts['not_observed'] += 1

    latest = rendered_source_rows[0] if rendered_source_rows else None
    return {
        'rows': rendered_rows,
        'pagination': pagination,
        'latest_status': latest.health_status if latest else 'not_observed',
        'latest_readiness': latest.readiness if latest else 'validation_required',
        'latest_effective_status': (
            _effective_runtime_posture(latest.health_status, latest.readiness) if latest else 'not_observed'
        ),
        'latest_score': latest.health_score if latest else None,
        'health_counts': health_counts,
        'posture_counts': posture_counts,
    }



def _effective_runtime_posture(health_status: str | None, readiness: str | None) -> str:
    """Return the worst current posture across runtime health and readiness."""
    health = str(health_status or 'not_observed').strip().lower()
    ready = str(readiness or 'validation_required').strip().lower()
    if health == 'unhealthy' or ready == 'blocked':
        return 'blocked'
    if health == 'degraded' or ready == 'degraded':
        return 'degraded'
    if health == 'healthy' and ready == 'ready':
        return 'ready'
    return 'validation_required'


def _diagnostic_summary(detail: str, *, label: str = 'Diagnostic') -> str:
    value = ' '.join(str(detail or '').split())
    lowered = value.lower()
    label_lower = str(label or '').lower()
    subject = 'Kubernetes API' if 'kubernetes' in label_lower else 'Provider'
    if not value:
        return f'{label} evidence was not recorded.'
    if 'could not resolve' in lowered or 'name or service not known' in lowered or 'temporary failure in name resolution' in lowered:
        return f'{subject} hostname could not be resolved.'
    if 'connection refused' in lowered:
        return f'{subject} connection was refused.'
    if 'timed out' in lowered or 'timeout' in lowered:
        return f'{subject} request timed out.'
    if 'x509' in lowered or 'certificate verify failed' in lowered or 'tls certificate' in lowered:
        return f'{subject} TLS certificate validation failed.'
    if len(value) <= 140:
        return value
    clipped = value[:137].rsplit(' ', 1)[0].rstrip(' ,;:.')
    return f'{clipped}…'


def _runtime_primary_summary(
    *,
    provider: str,
    message: str,
    diagnostics: list[dict[str, object]],
) -> str:
    """Return one concise current finding without duplicating diagnostic detail."""
    priority = {'failed': 0, 'warning': 1, 'pending': 2, 'unknown': 3}
    candidates = sorted(
        diagnostics,
        key=lambda item: priority.get(str(item.get('status') or '').lower(), 9),
    )
    for item in candidates:
        if str(item.get('status') or '').lower() in priority:
            summary = str(item.get('summary') or '').strip()
            if summary:
                if provider == 'kubernetes' and summary.startswith('Provider '):
                    return 'Kubernetes API ' + summary[len('Provider '):]
                return summary
    if message:
        label = 'Kubernetes API' if provider == 'kubernetes' else 'Runtime'
        return _diagnostic_summary(message, label=label)
    return 'No current runtime issue was recorded.'

def _message_repeats_diagnostic(message: str, diagnostics: list[dict[str, object]]) -> bool:
    normalized = ' '.join(str(message or '').split()).strip().lower()
    if not normalized:
        return False
    for item in diagnostics:
        detail = ' '.join(str(item.get('detail') or '').split()).strip().lower()
        if not detail:
            continue
        if normalized == detail or normalized in detail or detail in normalized:
            return True
    return False

def _diagnostic_rows(items: list[object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in items:
        if isinstance(item, Mapping):
            status = str(item.get('status') or 'unknown')
            rows.append(
                {
                    'key': str(item.get('key') or ''),
                    'label': str(item.get('label') or present_key_label(str(item.get('key') or 'Diagnostic'))),
                    'category': str(item.get('category') or ''),
                    'category_label': present_key_label(str(item.get('category') or 'runtime')),
                    'status': status,
                    'status_label': present_key_label(status),
                    'detail': str(item.get('detail') or 'No diagnostic detail was recorded.'),
                    'summary': _diagnostic_summary(
                        str(item.get('detail') or 'No diagnostic detail was recorded.'),
                        label=str(item.get('label') or present_key_label(str(item.get('key') or 'Diagnostic'))),
                    ),
                    'severity': str(item.get('severity') or 'info'),
                    'recommendation': str(item.get('recommendation') or ''),
                    'duration_ms': item.get('duration_ms'),
                    'duration_display': present_milliseconds(item.get('duration_ms')),
                }
            )
    return rows


def _kubernetes_lifecycle_context(provider: str, metadata: Mapping[str, Any] | None) -> dict[str, object] | None:
    if provider != 'kubernetes':
        return None
    metadata = metadata or {}
    version = str(metadata.get('version') or '')
    policy = metadata.get('lifecycle_policy')
    if not isinstance(policy, Mapping):
        policy = kubernetes_lifecycle_policy(version)
    selected_adapters = metadata.get('selected_adapters') or {}
    stable_apis: list[str] = []
    legacy_apis: list[str] = []
    if isinstance(selected_adapters, Mapping):
        for feature_key, adapter in selected_adapters.items():
            if not isinstance(adapter, Mapping):
                continue
            group = str(adapter.get('group') or '')
            api_version = str(adapter.get('version') or '')
            resource = str(adapter.get('resource') or '')
            api = f'{group}/{api_version}' if group else api_version
            label = f'{api} · {resource}' if resource else api
            if str(adapter.get('stability') or 'stable') == 'legacy':
                legacy_apis.append(label)
            else:
                stable_apis.append(label)
    return {
        'detected_version': str(policy.get('detected_version') or (f'v{version}' if version else 'Unknown')),
        'lifecycle_status': str(metadata.get('lifecycle_status') or policy.get('lifecycle_status') or 'unknown'),
        'lifecycle_status_label': present_key_label(
            str(metadata.get('lifecycle_status') or policy.get('lifecycle_status') or 'unknown')
        ),
        'current_version_band': str(policy.get('current_version_band') or 'Not defined'),
        'supported_version_band': str(policy.get('supported_version_band') or 'Not defined'),
        'supported_constraint': str(policy.get('supported_constraint') or 'Not defined'),
        'stable_apis': sorted(stable_apis),
        'legacy_apis': sorted(legacy_apis),
        'stable_api_count': len(stable_apis),
        'legacy_api_count': len(legacy_apis),
        'readiness_reasons': [str(item) for item in (metadata.get('readiness_reasons') or []) if item],
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


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
