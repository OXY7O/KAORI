from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.alertmanager.consumer import list_alerts_for_scope
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.integrations.binding_selectors import apply_promql_scope
from app.integrations.prometheus.exceptions import (
    PrometheusAuthenticationError,
    PrometheusConnectionError,
    PrometheusError,
)
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem
from app.prometheus.consumer import PrometheusConsumer

ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'prometheus')
_OBJECT_STORAGE_SCOPE = 'object_storage_system'
_PROMETHEUS_ALERTS_QUERY = 'ALERTS{alertstate=~"firing|pending"}'


@dataclass(frozen=True, slots=True)
class AlertSourceRuntime:
    configured: bool
    connected: bool
    label: str
    tone: str
    detail: str


def selected_alert_source(query_args: Any) -> str:
    value = str(query_args.get('source') or 'auto').strip().lower()
    return value if value in ALERT_SOURCE_OPTIONS else 'auto'


def load_alert_stream(system: ObjectStorageSystem, *, selected_source: str) -> dict[str, Any]:
    if selected_source == 'alertmanager':
        return _load_alertmanager(system, selected_source='alertmanager')
    if selected_source == 'prometheus':
        return _load_prometheus(system, selected_source='prometheus')

    alertmanager = _load_alertmanager(system, selected_source='auto')
    if alertmanager['connected']:
        return alertmanager

    prometheus = _load_prometheus(system, selected_source='auto')
    if prometheus['connected']:
        prometheus['fallback_used'] = True
        prometheus['label'] = 'Prometheus Fallback Active'
        prometheus['tone'] = 'warning'
        prometheus['fallback_reason'] = (
            f'Alertmanager was not usable: {alertmanager.get("detail") or alertmanager.get("label")}. '
            'Prometheus ALERTS evidence is being used for the current view.'
        )
        return prometheus

    configured = bool(alertmanager['configured'] or prometheus['configured'])
    return _source_view(
        selected_source='auto',
        resolved_source='none',
        runtime=AlertSourceRuntime(
            configured=configured,
            connected=False,
            label='Alert Sources Unavailable' if configured else 'Alert Sources Not Configured',
            tone='critical' if configured else 'unknown',
            detail=(
                f'Alertmanager: {alertmanager.get("detail") or alertmanager.get("label")}. '
                f'Prometheus: {prometheus.get("detail") or prometheus.get("label")}.'
            ),
        ),
        rows=[],
        instance_name=None,
    )


def alertmanager_readiness(
    system: ObjectStorageSystem,
    *,
    runtime_stream: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolution = resolve_alertmanager_sources(
        scope_type=_OBJECT_STORAGE_SCOPE,
        scope_key=str(system.id),
        required_capabilities=('alerts_v2',),
    )
    if not resolution.candidates:
        return {
            'configured': False,
            'connected': False,
            'label': 'Not Configured',
            'tone': 'unknown',
            'description': 'No Alertmanager source is bound to this Object Storage system.',
            'instance_name': None,
            'profile': 'object-storage-alerts-v1',
        }

    selected = resolution.selected
    if selected is None:
        candidate = resolution.candidates[0]
        return {
            'configured': True,
            'connected': False,
            'label': _ineligible_label(candidate.decision_reason),
            'tone': 'warning',
            'description': candidate.decision_reason,
            'instance_name': candidate.instance.name,
            'profile': candidate.binding.validation_profile or 'object-storage-alerts-v1',
        }

    if (
        runtime_stream is not None
        and runtime_stream.get('resolved_source') == 'alertmanager'
        and runtime_stream.get('connected')
    ):
        return {
            'configured': True,
            'connected': True,
            'label': 'Operational',
            'tone': 'normal',
            'description': 'Alertmanager consumer binding is eligible and the current alert retrieval succeeded.',
            'instance_name': runtime_stream.get('instance_name') or selected.instance.name,
            'profile': selected.binding.validation_profile or 'object-storage-alerts-v1',
        }

    runtime_state = str(selected.instance.last_status or '').strip().lower()
    connected = runtime_state == 'connected'
    runtime_failed = runtime_state in {'disconnected', 'error', 'failed', 'unhealthy'}
    if connected:
        label, tone = 'Operational', 'normal'
        description = 'Alertmanager consumer binding is eligible and the latest runtime observation is connected.'
    elif runtime_failed:
        label, tone = 'Disconnected', 'critical'
        description = (
            selected.instance.last_error
            or 'Alertmanager consumer binding is eligible but the latest runtime observation is disconnected.'
        )
    else:
        label, tone = 'Ready · Runtime Unverified', 'info'
        description = (
            'Alertmanager consumer binding is eligible. Runtime connectivity will be confirmed when alerts are loaded.'
        )
    return {
        'configured': True,
        'connected': connected,
        'label': label,
        'tone': tone,
        'description': description,
        'instance_name': selected.instance.name,
        'profile': selected.binding.validation_profile or 'object-storage-alerts-v1',
    }


def build_alert_posture(stream: dict[str, Any]) -> dict[str, Any]:
    rows = stream.get('rows') or []
    counts = {
        'total': len(rows),
        'critical': sum(row.get('severity') == 'critical' for row in rows),
        'warning': sum(row.get('severity') == 'warning' for row in rows),
        'info': sum(row.get('severity') == 'info' for row in rows),
        'firing': sum(row.get('state') == 'firing' for row in rows),
        'pending': sum(row.get('state') == 'pending' for row in rows),
        'silenced': sum(bool(row.get('silenced')) for row in rows),
        'inhibited': sum(bool(row.get('inhibited')) for row in rows),
    }
    if not stream.get('connected'):
        status, tone = 'Unknown', 'unknown'
        detail = 'Active alert posture cannot be evaluated because the selected alert source is unavailable.'
    elif counts['critical']:
        status, tone = 'Critical', 'critical'
        detail = 'One or more critical active alerts require immediate operational triage.'
    elif counts['warning']:
        status, tone = 'Attention', 'warning'
        detail = 'Active warning alerts require planned operational review.'
    elif counts['total']:
        status, tone = 'Active', 'info'
        detail = 'Active alerts are present without critical or warning severity evidence.'
    else:
        status, tone = 'No Active Alerts', 'normal'
        detail = 'The selected alert source is operational and currently returns no active alerts for this Object Storage system.'
    return {
        **counts,
        'status': status,
        'tone': tone,
        'detail': detail,
    }


def _load_alertmanager(system: ObjectStorageSystem, *, selected_source: str) -> dict[str, Any]:
    resolution = resolve_alertmanager_sources(
        scope_type=_OBJECT_STORAGE_SCOPE,
        scope_key=str(system.id),
        required_capabilities=('alerts_v2',),
    )
    if not resolution.candidates:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=False,
                connected=False,
                label='Alertmanager Not Configured',
                tone='unknown',
                detail='No Alertmanager source is bound to this Object Storage system.',
            ),
            rows=[],
            instance_name=None,
        )
    if resolution.selected is None:
        candidate = resolution.candidates[0]
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=True,
                connected=False,
                label=_ineligible_label(candidate.decision_reason),
                tone='warning',
                detail=candidate.decision_reason,
            ),
            rows=[],
            instance_name=candidate.instance.name,
        )

    result = list_alerts_for_scope(
        scope_type=_OBJECT_STORAGE_SCOPE,
        scope_key=str(system.id),
        required_capabilities=('alerts_v2',),
    )
    selected = resolution.selected
    if not result.get('connected'):
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=True,
                connected=False,
                label='Alertmanager Disconnected',
                tone='critical',
                detail=str(result.get('error') or 'Alertmanager alert retrieval failed.'),
            ),
            rows=[],
            instance_name=selected.instance.name,
        )

    rows = _deduplicate(_alertmanager_rows(result.get('alerts') or []))
    return _source_view(
        selected_source=selected_source,
        resolved_source='alertmanager',
        runtime=AlertSourceRuntime(
            configured=True,
            connected=True,
            label='Operational',
            tone='normal',
            detail='Alertmanager is the active alert source for this Object Storage system.',
        ),
        rows=rows,
        instance_name=str(result.get('source_instance_name') or selected.instance.name),
    )


def _load_prometheus(system: ObjectStorageSystem, *, selected_source: str) -> dict[str, Any]:
    configured = _provider_bound(system.id, 'prometheus')
    try:
        consumer = PrometheusConsumer.for_asset(
            scope_type=_OBJECT_STORAGE_SCOPE,
            scope_key=system.id,
            scope_name=system.name,
        )
        query = apply_promql_scope(_PROMETHEUS_ALERTS_QUERY, consumer.binding.selector_json)
        payload = consumer.query(query, retry_count=0)
    except PrometheusAuthenticationError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Prometheus Authentication Failed',
                tone='critical',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )
    except PrometheusConnectionError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Prometheus Disconnected',
                tone='critical',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )
    except PrometheusError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Prometheus Validation Required' if configured else 'Prometheus Not Configured',
                tone='warning' if configured else 'unknown',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )

    rows = _deduplicate(_prometheus_rows(payload))
    return _source_view(
        selected_source=selected_source,
        resolved_source='prometheus',
        runtime=AlertSourceRuntime(
            configured=True,
            connected=True,
            label='Operational',
            tone='normal',
            detail='Prometheus ALERTS metric is the active alert source for this Object Storage system.',
        ),
        rows=rows,
        instance_name=consumer.config.name,
    )


def _source_view(
    *,
    selected_source: str,
    resolved_source: str,
    runtime: AlertSourceRuntime,
    rows: list[dict[str, Any]],
    instance_name: str | None,
) -> dict[str, Any]:
    return {
        'selected_source': selected_source,
        'resolved_source': resolved_source,
        'resolved_label': _source_label(resolved_source),
        'configured': runtime.configured,
        'connected': runtime.connected,
        'label': runtime.label,
        'tone': runtime.tone,
        'detail': runtime.detail,
        'rows': rows,
        'instance_name': instance_name,
        'fallback_used': False,
        'fallback_reason': None,
        'checked_at': datetime.now(UTC),
    }


def _provider_bound(system_id: str, provider_type: str) -> bool:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationBinding.asset_type == _OBJECT_STORAGE_SCOPE,
            IntegrationBinding.asset_key == str(system_id),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.provider_type == provider_type,
            IntegrationInstance.enabled.is_(True),
        )
        .first()
        is not None
    )


def _alertmanager_rows(items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        labels = item.get('labels') if isinstance(item.get('labels'), dict) else {}
        rows.append(
            {
                'name': str(item.get('alert_name') or item.get('alertname') or 'Unknown Alert'),
                'severity': _severity(item.get('severity')),
                'state': _state(item.get('state') or item.get('status')),
                'target': _target(labels),
                'summary': str(item.get('summary') or item.get('description') or '-'),
                'starts_at': item.get('starts_at'),
                'receiver': str(item.get('receiver') or '-'),
                'silenced': bool(item.get('silenced')),
                'inhibited': bool(item.get('inhibited')),
                'source': 'Alertmanager',
                'source_key': 'alertmanager',
                'fingerprint': str(item.get('fingerprint') or ''),
                'labels': labels,
            }
        )
    return rows


def _prometheus_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else None
    result = data.get('result') if isinstance(data, dict) else None
    if not isinstance(result, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        labels = item.get('metric') if isinstance(item.get('metric'), dict) else {}
        rows.append(
            {
                'name': str(labels.get('alertname') or 'Unknown Alert'),
                'severity': _severity(labels.get('severity')),
                'state': _state(labels.get('alertstate')),
                'target': _target(labels),
                'summary': str(labels.get('alertname') or 'Prometheus ALERTS metric'),
                'starts_at': None,
                'receiver': '-',
                'silenced': False,
                'inhibited': False,
                'source': 'Prometheus',
                'source_key': 'prometheus',
                'fingerprint': '',
                'labels': labels,
            }
        )
    return rows


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        labels = row.get('labels') if isinstance(row.get('labels'), dict) else {}
        fingerprint = str(row.get('fingerprint') or '').strip()
        identity: tuple[Any, ...]
        if fingerprint:
            identity = ('fingerprint', fingerprint)
        else:
            identity = (
                str(row.get('name') or '').casefold(),
                str(row.get('target') or '').casefold(),
                tuple(sorted((str(key), str(value)) for key, value in labels.items() if key != 'alertstate')),
            )
        selected.setdefault(identity, row)
    return list(selected.values())


def _target(labels: dict[str, Any]) -> str:
    for key in ('bucket', 'instance', 'job', 'deployment', 'server', 'node'):
        value = str(labels.get(key) or '').strip()
        if value:
            return value
    return '-'


def _severity(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'critical', 'error', 'fatal', 'p1'}:
        return 'critical'
    if normalized in {'warning', 'warn', 'p2'}:
        return 'warning'
    if normalized in {'info', 'informational', 'notice', 'p3', 'p4'}:
        return 'info'
    return 'unknown'


def _state(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'firing', 'active'}:
        return 'firing'
    if normalized in {'pending', 'unprocessed'}:
        return 'pending'
    if normalized in {'suppressed'}:
        return 'suppressed'
    if normalized in {'resolved', 'inactive'}:
        return 'resolved'
    return normalized or 'firing'


def _source_label(source: str) -> str:
    return {'alertmanager': 'Alertmanager', 'prometheus': 'Prometheus', 'none': 'Unavailable'}.get(
        source, source.title()
    )


def _ineligible_label(reason: str) -> str:
    lowered = reason.lower()
    if 'selector' in lowered:
        return 'Selector Required'
    if 'stale' in lowered or 'profile' in lowered:
        return 'Consumer Validation Stale'
    if 'validation' in lowered or 'readiness' in lowered or 'capabilit' in lowered:
        return 'Validation Required'
    return 'Alertmanager Unavailable'
