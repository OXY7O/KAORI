from __future__ import annotations

from typing import Any

from app.alertmanager.bindings import resolve_sources
from app.alertmanager.contracts import AlertQuery
from app.alertmanager.reader import read_alerts, read_silences
from app.alertmanager.repository import get_legacy_config_by_cluster_id
from app.alertmanager.sanitization import safe_endpoint

KUBERNETES_CLUSTER_SCOPE = 'kubernetes_cluster'


def list_alerts_for_scope(
    *,
    scope_type: str,
    scope_key: str,
    query: AlertQuery | None = None,
) -> dict[str, Any]:
    sources = resolve_sources(scope_type=scope_type, scope_key=scope_key)
    errors: list[str] = []
    for source in sources:
        result = read_alerts(
            source,
            source_name=source.name,
            query=query,
            canonical_instance_id=source.id,
        )
        if result.get('connected'):
            result['resolved_scope_type'] = scope_type
            result['resolved_scope_key'] = scope_key
            result['fallback_used'] = bool(errors)
            result['source_errors'] = errors
            return result
        errors.append(f'{source.name}: {result.get("error") or "Unavailable"}')

    if scope_type == KUBERNETES_CLUSTER_SCOPE and not sources:
        legacy = get_legacy_config_by_cluster_id(scope_key)
        if legacy is not None and legacy.endpoint:
            result = read_alerts(
                legacy,
                source_name='Legacy cluster Alertmanager',
                query=query,
                canonical_instance_id=None,
            )
            result['legacy_source'] = True
            result['resolved_scope_type'] = scope_type
            result['resolved_scope_key'] = scope_key
            return result

    return {
        'source': 'alertmanager',
        'connected': False,
        'alerts': [],
        'error': '; '.join(errors) if errors else 'No Alertmanager source is bound to this scope.',
        'source_errors': errors,
        'resolved_scope_type': scope_type,
        'resolved_scope_key': scope_key,
    }


def list_silences_for_scope(
    *,
    scope_type: str,
    scope_key: str,
) -> dict[str, Any]:
    sources = resolve_sources(scope_type=scope_type, scope_key=scope_key)
    errors: list[str] = []
    for source in sources:
        result = read_silences(
            source,
            source_name=source.name,
            canonical_instance_id=source.id,
        )
        if result.get('connected'):
            result['resolved_scope_type'] = scope_type
            result['resolved_scope_key'] = scope_key
            result['fallback_used'] = bool(errors)
            result['source_errors'] = errors
            return result
        errors.append(f'{source.name}: {result.get("error") or "Unavailable"}')

    if scope_type == KUBERNETES_CLUSTER_SCOPE and not sources:
        legacy = get_legacy_config_by_cluster_id(scope_key)
        if legacy is not None and legacy.endpoint:
            result = read_silences(
                legacy,
                source_name='Legacy cluster Alertmanager',
                canonical_instance_id=None,
            )
            result['legacy_source'] = True
            return result

    return {
        'source': 'alertmanager',
        'connected': False,
        'silences': [],
        'error': '; '.join(errors) if errors else 'No Alertmanager source is bound to this scope.',
        'source_errors': errors,
    }


def get_scope_status(*, scope_type: str, scope_key: str) -> dict[str, Any]:
    sources = resolve_sources(scope_type=scope_type, scope_key=scope_key)
    if sources:
        primary = sources[0]
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
            'source_count': len(sources),
            'legacy_source': False,
        }

    if scope_type == KUBERNETES_CLUSTER_SCOPE:
        legacy = get_legacy_config_by_cluster_id(scope_key)
        if legacy is not None and legacy.endpoint:
            return {
                'configured': True,
                'connected': legacy.last_status == 'connected',
                'label': legacy.display_status,
                'response_time_ms': legacy.last_response_time_ms,
                'last_checked_at': legacy.last_checked_at,
                'error': legacy.last_error,
                'instance_id': None,
                'instance_name': 'Legacy cluster Alertmanager',
                'endpoint': safe_endpoint(legacy.endpoint),
                'source_count': 1,
                'legacy_source': True,
            }

    return {
        'configured': False,
        'connected': False,
        'label': 'Not Configured',
        'response_time_ms': None,
        'last_checked_at': None,
        'error': None,
        'instance_id': None,
        'instance_name': None,
        'endpoint': None,
        'source_count': 0,
        'legacy_source': False,
    }
