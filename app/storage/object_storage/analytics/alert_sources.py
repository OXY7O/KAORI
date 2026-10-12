from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.integrations.binding_selectors import BindingSelectorError, apply_promql_scope, parse_matchers
from app.integrations.observability.alert_source.providers.alertmanager.application.consumer import (
    list_alerts_for_scope,
)
from app.integrations.observability.alert_source.providers.alertmanager.application.resolver import (
    resolve_alertmanager_sources,
)
from app.integrations.observability.metrics_source.application.consumer import MetricsConsumer
from app.integrations.observability.metrics_source.exceptions import (
    MetricsSourceAuthenticationError,
    MetricsSourceConnectionError,
    MetricsSourceError,
)
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.observability.metrics_source.query_profiles.alerts_v1 import ACTIVE_ALERTS_EXPRESSION
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem

ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'metrics_source')
_OBJECT_STORAGE_SCOPE = 'object_storage_system'


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
    if selected_source == 'metrics_source':
        return _load_metrics_source(system, selected_source='metrics_source')

    alertmanager = _load_alertmanager(system, selected_source='auto')
    if alertmanager['connected']:
        return alertmanager

    metrics_source = _load_metrics_source(system, selected_source='auto')
    if metrics_source['connected']:
        metrics_source['fallback_used'] = True
        metrics_source['label'] = 'Metrics Source Fallback Active'
        metrics_source['tone'] = 'warning'
        metrics_source['fallback_reason'] = (
            f'Alertmanager was not usable: {alertmanager.get("detail") or alertmanager.get("label")}. '
            'Metrics query evidence is being collected for the committed analytics snapshot.'
        )
        return metrics_source

    configured = bool(alertmanager['configured'] or metrics_source['configured'])
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
                f'Metrics Source: {metrics_source.get("detail") or metrics_source.get("label")}.'
            ),
        ),
        rows=[],
        instance_name=None,
    )


def resolve_materialized_alert_stream(
    streams: dict[str, Any],
    *,
    selected_source: str,
) -> dict[str, Any]:
    """Resolve a UI alert source from worker-collected streams without live provider access."""

    alertmanager = dict(streams.get('alertmanager') or {})
    metrics_source = dict(streams.get('metrics_source') or {})
    if selected_source == 'alertmanager':
        return alertmanager or _source_view(
            selected_source='alertmanager',
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=False,
                connected=False,
                label='Alertmanager Snapshot Unavailable',
                tone='unknown',
                detail='The committed analytics snapshot does not contain Alertmanager evidence.',
            ),
            rows=[],
            instance_name=None,
        )
    if selected_source == 'metrics_source':
        return metrics_source or _source_view(
            selected_source='metrics_source',
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=False,
                connected=False,
                label='Metrics Alert Snapshot Unavailable',
                tone='unknown',
                detail='The committed analytics snapshot does not contain metrics-backed alert evidence.',
            ),
            rows=[],
            instance_name=None,
        )

    if alertmanager.get('connected'):
        resolved = dict(alertmanager)
        resolved['selected_source'] = 'auto'
        return resolved
    if metrics_source.get('connected'):
        resolved = dict(metrics_source)
        resolved['selected_source'] = 'auto'
        resolved['fallback_used'] = True
        resolved['label'] = 'Metrics Source Fallback Active'
        resolved['tone'] = 'warning'
        resolved['fallback_reason'] = (
            f'Alertmanager was not usable in the committed snapshot: '
            f'{alertmanager.get("detail") or alertmanager.get("label") or "no alert evidence"}. '
            'Metrics-backed alert evidence is being used from the same analytics snapshot.'
        )
        return resolved

    configured = bool(alertmanager.get('configured') or metrics_source.get('configured'))
    return _source_view(
        selected_source='auto',
        resolved_source='none',
        runtime=AlertSourceRuntime(
            configured=configured,
            connected=False,
            label='Alert Sources Unavailable' if configured else 'Alert Sources Not Configured',
            tone='critical' if configured else 'unknown',
            detail=(
                f'Alertmanager snapshot: {alertmanager.get("detail") or alertmanager.get("label") or "unavailable"}. '
                f'Metrics Source snapshot: {metrics_source.get("detail") or metrics_source.get("label") or "unavailable"}.'
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
            'description': 'Alertmanager consumer binding is eligible and the analytics worker alert retrieval succeeded.',
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
        description = 'Alertmanager consumer binding is eligible. Runtime connectivity will be confirmed by the analytics worker refresh.'
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
        detail = 'The selected alert source is operational and currently reports no active alerts for this Object Storage system. This observed empty result is not proof of overall system health.'
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

    raw_alerts = result.get('alerts')
    if (
        result.get('error')
        or not isinstance(raw_alerts, list)
        or any(
            not isinstance(item, dict)
            or not str(item.get('alert_name') or item.get('alertname') or '').strip()
            or not isinstance(item.get('labels'), dict)
            for item in raw_alerts
        )
    ):
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=True,
                connected=False,
                label='Alertmanager Evidence Incomplete',
                tone='warning',
                detail='Alertmanager returned missing or malformed alert records; zero alerts cannot be confirmed.',
            ),
            rows=[],
            instance_name=selected.instance.name,
        )
    rows = _deduplicate(_alertmanager_rows(raw_alerts))
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


def _scoped_metrics_alert_expression(consumer: MetricsConsumer) -> str:
    """Require a unique positive asset binding, not merely a shared Metrics Source."""
    binding = consumer.binding
    matchers = parse_matchers(binding.selector_json)
    exact = {matcher.label: matcher.value for matcher in matchers if matcher.operator == '='}
    if not exact:
        raise BindingSelectorError(
            'The selected Object Storage metrics binding needs an exact asset label selector '
            'before it can supply system-scoped alert evidence.'
        )

    peers = IntegrationBinding.query.filter(
        IntegrationBinding.integration_instance_id == binding.integration_instance_id,
        IntegrationBinding.asset_type == _OBJECT_STORAGE_SCOPE,
        IntegrationBinding.enabled.is_(True),
        IntegrationBinding.id != binding.id,
    ).all()
    for peer in peers:
        peer_exact = {
            matcher.label: matcher.value
            for matcher in parse_matchers(peer.selector_json)
            if matcher.operator == '='
        }
        if not any(key in peer_exact and peer_exact[key] != value for key, value in exact.items()):
            raise BindingSelectorError(
                'Metrics Source asset selectors overlap another Object Storage binding; '
                'alerts cannot be uniquely attributed to this system.'
            )
    return apply_promql_scope(ACTIVE_ALERTS_EXPRESSION, binding.selector_json)


def _load_metrics_source(system: ObjectStorageSystem, *, selected_source: str) -> dict[str, Any]:
    configured = _provider_bound(system.id, 'metrics_source')
    try:
        consumer = MetricsConsumer.for_asset(
            scope_type=_OBJECT_STORAGE_SCOPE,
            scope_key=system.id,
            scope_name=system.name,
        )
        expression = _scoped_metrics_alert_expression(consumer)
        payload = consumer.query(expression, retry_count=0)
    except BindingSelectorError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Metrics Alert Scope Unverified',
                tone='warning',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )
    except MetricsSourceAuthenticationError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Metrics Source Authentication Failed',
                tone='critical',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )
    except MetricsSourceConnectionError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Metrics Source Disconnected',
                tone='critical',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )
    except MetricsSourceError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Metrics Source Validation Required' if configured else 'Metrics Source Not Configured',
                tone='warning' if configured else 'unknown',
                detail=str(exc),
            ),
            rows=[],
            instance_name=None,
        )

    provider = provider_definition(consumer.config.provider_key)
    try:
        rows = _deduplicate(_metrics_source_rows(payload, source_label=provider.label))
    except ValueError as exc:
        return _source_view(
            selected_source=selected_source,
            resolved_source='none',
            runtime=AlertSourceRuntime(
                configured=configured,
                connected=False,
                label='Metrics Alert Evidence Incomplete',
                tone='warning',
                detail=str(exc),
            ),
            rows=[],
            instance_name=consumer.config.name,
        )
    return _source_view(
        selected_source=selected_source,
        resolved_source='metrics_source',
        runtime=AlertSourceRuntime(
            configured=True,
            connected=True,
            label='Operational',
            tone='normal',
            detail=f'{provider.label} is the active metrics-backed alert source for this Object Storage system.',
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


def _provider_bound(system_id: str, integration_type: str) -> bool:
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationBinding.asset_type == _OBJECT_STORAGE_SCOPE,
            IntegrationBinding.asset_key == str(system_id),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.integration_type == integration_type,
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
        raw_labels = item.get('labels')
        labels: dict[str, Any] = dict(raw_labels) if isinstance(raw_labels, dict) else {}
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


def _metrics_source_rows(payload: dict[str, Any], *, source_label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get('status') != 'success':
        raise ValueError('Metrics Source did not return a successful Prometheus alert query envelope.')
    data = payload.get('data')
    result = data.get('result') if isinstance(data, dict) else None
    if not isinstance(result, list) or data.get('resultType', 'vector') != 'vector':
        raise ValueError('Metrics Source alert response is missing a complete instant-vector data.result array.')
    rows: list[dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get('metric'), dict):
            raise ValueError('Metrics Source alert response contains malformed alert series.')
        raw_labels = item['metric']
        if not str(raw_labels.get('alertname') or '').strip() or not str(raw_labels.get('alertstate') or '').strip():
            raise ValueError('Metrics Source alert response has a series without alertname or alertstate.')
        sample = item.get('value')
        if not isinstance(sample, (list, tuple)) or len(sample) < 2:
            raise ValueError('Metrics Source alert response has an incomplete sample.')
        labels: dict[str, Any] = dict(raw_labels)
        rows.append(
            {
                'name': str(labels.get('alertname') or 'Unknown Alert'),
                'severity': _severity(labels.get('severity')),
                'state': _state(labels.get('alertstate')),
                'target': _target(labels),
                'summary': str(labels.get('alertname') or 'Metrics alert evidence'),
                'starts_at': None,
                'receiver': '-',
                'silenced': False,
                'inhibited': False,
                'source': source_label,
                'source_key': 'metrics_source',
                'fingerprint': '',
                'labels': labels,
            }
        )
    return rows


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        raw_labels = row.get('labels')
        labels: dict[str, Any] = dict(raw_labels) if isinstance(raw_labels, dict) else {}
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
    return {'alertmanager': 'Alertmanager', 'metrics_source': 'Metrics Source', 'none': 'Unavailable'}.get(
        source, source.replace('_', ' ').title()
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
