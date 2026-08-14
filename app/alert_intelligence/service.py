from __future__ import annotations

from typing import Any

from werkzeug.datastructures import MultiDict

from app.analytics.kubernetes.alerts.sources import load_alerts_by_source
from app.analytics.object_storage.alert_sources import load_alert_stream
from app.common.pagination import paginate_sequence
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.service import get_active_recommendation_findings
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem
from app.notification_channels.service import notification_channel_summary, recent_delivery_summary

_VALID_DOMAINS = {'kubernetes', 'object_storage'}
_VALID_SOURCES = {'auto', 'alertmanager', 'prometheus'}
_VALID_SEVERITIES = {'all', 'critical', 'warning', 'info', 'unknown', 'none'}
_VALID_STATES = {'all', 'firing', 'pending', 'active', 'resolved'}
_VALID_TABS = {'overview', 'records', 'correlation', 'delivery', 'evidence'}
_DOMAIN_LABELS = {'kubernetes': 'Kubernetes', 'object_storage': 'Object Storage'}


def get_alert_intelligence_payload(args: MultiDict[str, str]) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    systems = ObjectStorageSystem.query.order_by(ObjectStorageSystem.name.asc()).all()
    domain = _selected_domain(args, clusters=clusters, systems=systems)
    assets = _asset_options(domain, clusters=clusters, systems=systems)
    selected_asset_key = _selected_asset_key(args, assets)
    selected_asset = _resolve_asset(domain, selected_asset_key, clusters=clusters, systems=systems)
    source = _choice(args.get('source'), _VALID_SOURCES, 'auto')
    tab = _choice(args.get('tab'), _VALID_TABS, 'overview')

    rows, source_status = _load_rows(domain, selected_asset, source=source)
    severity = _choice(args.get('severity'), _VALID_SEVERITIES, 'all')
    state = _choice(args.get('state'), _VALID_STATES, 'all')
    search = str(args.get('q') or '').strip()
    filtered = _filter_rows(rows, severity=severity, state=state, search=search)
    page_rows, pagination = paginate_sequence(
        filtered,
        page=args.get('page', 1),
        per_page=args.get('per_page', 5),
    )

    recommendations = (
        get_active_recommendation_findings(domain=domain, asset_key=selected_asset_key, limit=8)
        if selected_asset_key
        else []
    )
    catalog_rules = _alert_intelligence_rules(domain)
    notification_summary = notification_channel_summary()
    posture = _posture(rows, source_status)
    selected_asset_name = str(getattr(selected_asset, 'name', '') or 'No Asset Selected')
    return {
        'domain': domain,
        'domain_label': _DOMAIN_LABELS[domain],
        'domain_options': [
            {'value': 'kubernetes', 'label': 'Kubernetes', 'count': len(clusters)},
            {'value': 'object_storage', 'label': 'Object Storage', 'count': len(systems)},
        ],
        'assets': assets,
        'selected_asset_key': selected_asset_key,
        'selected_asset_name': selected_asset_name,
        'selected_asset_available': selected_asset is not None,
        'source': source,
        'tab': tab,
        'source_options': [
            {'value': 'auto', 'label': 'Automatic · Alertmanager Preferred'},
            {'value': 'alertmanager', 'label': 'Alertmanager'},
            {'value': 'prometheus', 'label': 'Prometheus'},
        ],
        'source_status': source_status,
        'posture': posture,
        'summary': {
            'active': len(rows),
            'critical': sum(row.get('severity') == 'critical' for row in rows),
            'warning': sum(row.get('severity') == 'warning' for row in rows),
            'recommendations': len(recommendations),
            'catalog_rules': len(catalog_rules),
        },
        'filters': {'severity': severity, 'state': state, 'q': search},
        'alerts': page_rows,
        'pagination': pagination,
        'recommendations': recommendations,
        'catalog_rules': catalog_rules,
        'notification': notification_summary,
        'recent_deliveries': recent_delivery_summary(limit=6, event_types=('alert_intelligence.active_alert',)),
        'ownership': {
            'detection': 'Prometheus evaluates alert rules and exposes ALERTS state.',
            'lifecycle': (
                'Alertmanager owns grouping, inhibition, routing, silences, receivers, '
                'and raw alert notification delivery.'
            ),
            'intelligence': (
                'KAORI resolves asset identity, adds committed context, correlates recommendations, '
                'and can send enriched Intelligence notifications through configured channels.'
            ),
            'automation': (
                'Automation Control remains a separately governed execution boundary and is not triggered '
                'by notification delivery.'
            ),
        },
    }


def list_active_alert_events() -> list[dict[str, Any]]:
    """Return active alert events across supported domains for notification dispatch."""
    events: list[dict[str, Any]] = []
    for cluster in Cluster.query.order_by(Cluster.id.asc()).all():
        rows, status = _load_rows('kubernetes', cluster, source='auto')
        if not status.get('connected'):
            continue
        recommendations = get_active_recommendation_findings(domain='kubernetes', asset_key=cluster.id, limit=5)
        for row in rows:
            if row.get('state') in {'firing', 'pending', 'active'}:
                events.append(
                    {
                        'domain': 'kubernetes',
                        'asset_type': 'kubernetes_cluster',
                        'asset_key': str(cluster.id),
                        'asset_name': cluster.name,
                        'alert': row,
                        'recommendations': recommendations,
                    }
                )
    for system in ObjectStorageSystem.query.order_by(ObjectStorageSystem.id.asc()).all():
        rows, status = _load_rows('object_storage', system, source='auto')
        if not status.get('connected'):
            continue
        recommendations = get_active_recommendation_findings(domain='object_storage', asset_key=system.id, limit=5)
        for row in rows:
            if row.get('state') in {'firing', 'pending', 'active'}:
                events.append(
                    {
                        'domain': 'object_storage',
                        'asset_type': 'object_storage_system',
                        'asset_key': str(system.id),
                        'asset_name': system.name,
                        'alert': row,
                        'recommendations': recommendations,
                    }
                )
    return events


def _selected_domain(
    args: MultiDict[str, str], *, clusters: list[Cluster], systems: list[ObjectStorageSystem]
) -> str:
    requested = str(args.get('domain') or '').strip().lower()
    if requested in _VALID_DOMAINS:
        return requested
    if clusters:
        return 'kubernetes'
    if systems:
        return 'object_storage'
    return 'kubernetes'


def _asset_options(
    domain: str, *, clusters: list[Cluster], systems: list[ObjectStorageSystem]
) -> list[dict[str, str]]:
    records = clusters if domain == 'kubernetes' else systems
    return [
        {
            'value': str(item.id),
            'label': str(item.name),
            'environment': str(item.environment or '-'),
        }
        for item in records
    ]


def _selected_asset_key(args: MultiDict[str, str], assets: list[dict[str, str]]) -> str:
    requested = str(args.get('asset') or '').strip()
    valid = {item['value'] for item in assets}
    if requested in valid:
        return requested
    return assets[0]['value'] if assets else ''


def _resolve_asset(
    domain: str,
    asset_key: str,
    *,
    clusters: list[Cluster],
    systems: list[ObjectStorageSystem],
) -> Cluster | ObjectStorageSystem | None:
    records: list[Cluster] | list[ObjectStorageSystem] = clusters if domain == 'kubernetes' else systems
    return next((item for item in records if str(item.id) == asset_key), None)


def _load_rows(
    domain: str,
    asset: Cluster | ObjectStorageSystem | None,
    *,
    source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if asset is None:
        return [], {
            'selected_source': source,
            'resolved_source': 'none',
            'label': 'No Asset Available',
            'configured': False,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': 'No asset is available in the selected domain.',
        }
    if domain == 'kubernetes':
        raw_rows, status = load_alerts_by_source(cluster=asset, source=source)  # type: ignore[arg-type]
        rows = [_normalize_kubernetes_row(row) for row in raw_rows]
        return rows, _normalize_source_status(status)
    stream = load_alert_stream(asset, selected_source=source)  # type: ignore[arg-type]
    return [_normalize_object_storage_row(row) for row in stream.get('rows') or []], _normalize_source_status(stream)


def _normalize_kubernetes_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'name': str(row.get('name') or 'Unknown Alert'),
        'severity': str(row.get('severity') or 'none'),
        'state': str(row.get('status') or 'active'),
        'target': str(row.get('target') or '-'),
        'namespace': str(row.get('namespace') or '-'),
        'summary': str(row.get('summary') or row.get('description') or '-'),
        'source': str(row.get('source') or '-'),
        'receiver': str(row.get('receiver') or '-'),
        'silenced': bool(row.get('silenced')),
        'inhibited': bool(row.get('inhibited')),
        'fingerprint': str(row.get('fingerprint') or ''),
        'starts_at': row.get('starts_at'),
        'starts_at_display': str(row.get('starts_at_display') or '-'),
        'labels': row.get('labels') if isinstance(row.get('labels'), dict) else {},
    }


def _normalize_object_storage_row(row: dict[str, Any]) -> dict[str, Any]:
    starts_at = row.get('starts_at')
    return {
        'name': str(row.get('name') or 'Unknown Alert'),
        'severity': str(row.get('severity') or 'unknown'),
        'state': str(row.get('state') or 'active'),
        'target': str(row.get('target') or '-'),
        'namespace': '-',
        'summary': str(row.get('summary') or '-'),
        'source': str(row.get('source') or '-'),
        'receiver': str(row.get('receiver') or '-'),
        'silenced': bool(row.get('silenced')),
        'inhibited': bool(row.get('inhibited')),
        'fingerprint': str(row.get('fingerprint') or ''),
        'starts_at': starts_at,
        'starts_at_display': str(starts_at or '-')[:16] if starts_at else '-',
        'labels': row.get('labels') if isinstance(row.get('labels'), dict) else {},
    }


def _normalize_source_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        'selected_source': str(status.get('selected_source') or status.get('source') or 'auto'),
        'resolved_source': str(status.get('resolved_source') or 'none'),
        'resolved_label': str(status.get('resolved_label') or _resolved_source_label(status.get('resolved_source'))),
        'label': str(status.get('label') or 'Unknown'),
        'configured': bool(status.get('configured')),
        'connected': bool(status.get('connected')),
        'fallback_used': bool(status.get('fallback_used')),
        'fallback_reason': status.get('fallback_reason'),
        'error': status.get('error') or status.get('detail'),
        'instance_name': status.get('instance_name'),
    }


def _filter_rows(
    rows: list[dict[str, Any]], *, severity: str, state: str, search: str
) -> list[dict[str, Any]]:
    filtered = rows
    if severity != 'all':
        filtered = [row for row in filtered if str(row.get('severity') or '').lower() == severity]
    if state != 'all':
        filtered = [row for row in filtered if str(row.get('state') or '').lower() == state]
    if search:
        needle = search.casefold()
        filtered = [
            row
            for row in filtered
            if needle
            in ' '.join(
                [
                    str(row.get('name') or ''),
                    str(row.get('target') or ''),
                    str(row.get('summary') or ''),
                    str(row.get('receiver') or ''),
                ]
            ).casefold()
        ]
    return filtered


def _posture(rows: list[dict[str, Any]], source_status: dict[str, Any]) -> dict[str, str]:
    if not source_status.get('connected'):
        return {'label': 'Evidence Unavailable', 'tone': 'unknown'}
    if any(row.get('severity') == 'critical' for row in rows):
        return {'label': 'Critical', 'tone': 'critical'}
    if any(row.get('severity') == 'warning' for row in rows):
        return {'label': 'Attention', 'tone': 'warning'}
    if rows:
        return {'label': 'Active', 'tone': 'info'}
    return {'label': 'No Active Alerts', 'tone': 'normal'}


def _alert_intelligence_rules(domain: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for rule in INTELLIGENCE_CATALOG:
        if str(rule.get('domain') or '') != domain:
            continue
        visible_in = rule.get('visible_in') if isinstance(rule.get('visible_in'), list) else []
        if 'Alert Intelligence' not in visible_in:
            continue
        rules.append(
            {
                'rule_key': str(rule.get('rule_key') or ''),
                'title': str(rule.get('title') or 'Untitled Rule'),
                'severity': str(rule.get('severity') or 'info'),
                'priority': str(rule.get('priority') or '-'),
                'rule_type': str(rule.get('logic_type') or '').replace('_', ' ').title(),
                'summary': str(rule.get('summary') or ''),
                'recommended_action': str(rule.get('recommended_action') or ''),
                'evidence_boundary': str(rule.get('evidence_boundary') or ''),
            }
        )
    return rules


def _choice(value: Any, valid: set[str], default: str) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in valid else default


def _resolved_source_label(value: Any) -> str:
    return {'alertmanager': 'Alertmanager', 'prometheus': 'Prometheus', 'none': 'None'}.get(
        str(value or 'none'), 'Unknown'
    )
