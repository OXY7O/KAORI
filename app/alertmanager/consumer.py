from __future__ import annotations

from typing import Any

from app.integrations.alertmanager.contracts import AlertQuery
from app.integrations.alertmanager.reader import read_alerts, read_silences
from app.alertmanager.resolver import AlertmanagerSourceResolution, resolve_alertmanager_sources
from app.alertmanager.sanitization import safe_endpoint
from app.integrations.binding_selectors import selector_filters

KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def list_alerts_for_scope(
    *,
    scope_type: str,
    scope_key: str,
    query: AlertQuery | None = None,
    required_capabilities: tuple[str, ...] = ('alerts_v2',),
) -> dict[str, Any]:
    resolution = resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )
    errors: list[str] = []
    for candidate in resolution.eligible_candidates:
        source = candidate.instance
        scoped_query = _merge_alert_query(query, candidate.binding.selector_json)
        result = read_alerts(
            source,
            source_name=source.name,
            query=scoped_query,
            canonical_instance_id=source.id,
        )
        if result.get('connected'):
            return _decorate_result(
                result,
                resolution=resolution,
                selected_instance_id=source.id,
                errors=errors,
            )
        errors.append(f'{source.name}: {result.get("error") or "Unavailable"}')

    rejected = [
        f'{candidate.instance.name}: {candidate.decision_reason}'
        for candidate in resolution.candidates
        if not candidate.eligible
    ]
    all_errors = [*errors, *rejected]
    return {
        'source': 'alertmanager',
        'connected': False,
        'alerts': [],
        'error': '; '.join(all_errors) if all_errors else 'No Alertmanager source is bound to this scope.',
        'source_errors': all_errors,
        'resolved_scope_type': scope_type,
        'resolved_scope_key': scope_key,
        'source_resolution': resolution.to_dict(),
    }


def list_silences_for_scope(
    *,
    scope_type: str,
    scope_key: str,
    required_capabilities: tuple[str, ...] = ('silences_v2',),
) -> dict[str, Any]:
    resolution = resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )
    errors: list[str] = []
    for candidate in resolution.eligible_candidates:
        source = candidate.instance
        result = read_silences(
            source,
            source_name=source.name,
            filters=selector_filters(candidate.binding.selector_json),
            canonical_instance_id=source.id,
        )
        if result.get('connected'):
            return _decorate_result(
                result,
                resolution=resolution,
                selected_instance_id=source.id,
                errors=errors,
            )
        errors.append(f'{source.name}: {result.get("error") or "Unavailable"}')

    rejected = [
        f'{candidate.instance.name}: {candidate.decision_reason}'
        for candidate in resolution.candidates
        if not candidate.eligible
    ]
    all_errors = [*errors, *rejected]
    return {
        'source': 'alertmanager',
        'connected': False,
        'silences': [],
        'error': '; '.join(all_errors) if all_errors else 'No Alertmanager source is bound to this scope.',
        'source_errors': all_errors,
        'source_resolution': resolution.to_dict(),
    }


def get_scope_status(*, scope_type: str, scope_key: str) -> dict[str, Any]:
    resolution = resolve_alertmanager_sources(scope_type=scope_type, scope_key=scope_key)
    selected = resolution.selected
    if selected is not None:
        primary = selected.instance
        return {
            'configured': bool(primary.endpoint),
            'connected': primary.last_status == 'connected',
            'label': primary.display_status,
            'response_time_ms': primary.last_response_time_ms,
            'last_checked_at': primary.last_checked_at,
            'error': primary.last_error,
            'instance_id': primary.id,
            'instance_name': primary.name,
            'endpoint': safe_endpoint(primary.endpoint),
            'source_count': len(resolution.eligible_candidates),
            'legacy_source': False,
            'source_resolution': resolution.to_dict(),
        }

    return {
        'configured': bool(resolution.candidates),
        'connected': False,
        'label': 'Unavailable' if resolution.candidates else 'Not Configured',
        'response_time_ms': None,
        'last_checked_at': None,
        'error': _resolution_error(resolution),
        'instance_id': None,
        'instance_name': None,
        'endpoint': None,
        'source_count': 0,
        'legacy_source': False,
        'source_resolution': resolution.to_dict(),
    }


def _decorate_result(
    result: dict[str, Any],
    *,
    resolution: AlertmanagerSourceResolution,
    selected_instance_id: int,
    errors: list[str],
) -> dict[str, Any]:
    selected_index = next(
        (
            index
            for index, candidate in enumerate(resolution.eligible_candidates)
            if candidate.instance.id == selected_instance_id
        ),
        0,
    )
    result['resolved_scope_type'] = resolution.scope_type
    result['resolved_scope_key'] = resolution.scope_key
    result['fallback_used'] = selected_index > 0 or bool(errors)
    result['source_errors'] = errors
    result['source_resolution'] = resolution.to_dict()
    selected = next(
        (candidate for candidate in resolution.eligible_candidates if candidate.instance.id == selected_instance_id),
        None,
    )
    result['selected_source'] = selected.to_dict() if selected is not None else None
    return result


def _resolution_error(resolution: AlertmanagerSourceResolution) -> str | None:
    if not resolution.candidates:
        return None
    reasons = [candidate.decision_reason for candidate in resolution.candidates if not candidate.eligible]
    return '; '.join(reasons) if reasons else 'No eligible Alertmanager source is currently available.'


def _merge_alert_query(query: AlertQuery | None, selector_json: dict | None) -> AlertQuery:
    base = query or AlertQuery()
    binding_filters = selector_filters(selector_json)
    if not binding_filters:
        return base
    return AlertQuery(
        active=base.active,
        silenced=base.silenced,
        inhibited=base.inhibited,
        unprocessed=base.unprocessed,
        receiver=base.receiver,
        filters=tuple(dict.fromkeys((*binding_filters, *base.filters))),
    )
