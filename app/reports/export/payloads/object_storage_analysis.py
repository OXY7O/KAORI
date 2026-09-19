from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from werkzeug.datastructures import MultiDict

from app.extensions.db import db
from app.models.object_storage import ObjectStorageSystem
from app.models.report import Report
from app.reports.catalog import require_object_storage_system, validate_report_instance
from app.storage.object_storage.analytics.service import get_object_storage_analytics_context


def _blocker_detail(context: dict[str, Any]) -> str:
    blocker = context.get('dependency_blocker')
    if isinstance(blocker, dict):
        return str(blocker.get('description') or blocker.get('detail') or blocker.get('message') or '').strip()
    return ''


def _source_status(context: dict[str, Any]) -> dict[str, Any]:
    raw_source = context.get('metrics_source')
    source: dict[str, Any] = dict(raw_source) if isinstance(raw_source, dict) else {}
    blocker_detail = _blocker_detail(context)
    label = str(source.get('label') or ('Limited' if blocker_detail else 'Ready'))
    return {
        'label': label,
        'status': label,
        'description': blocker_detail or str(source.get('detail') or 'Object Storage metrics evidence collected.'),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _alert_rows(alerts: dict[str, Any]) -> list[Any]:
    alert_table = _mapping(alerts.get('alert_table'))
    rows = list(alert_table.get('rows') or [])
    if rows:
        return rows
    return list(_mapping(alerts.get('alert_source')).get('rows') or [])


def _capacity_usage(metrics: dict[str, Any]) -> dict[str, Any]:
    existing = metrics.get('capacity_usage')
    if isinstance(existing, dict):
        return existing
    return {
        'capacity_total': metrics.get('capacity_total_display'),
        'usage_total': metrics.get('usage_total_display'),
        'capacity_free': metrics.get('capacity_free_display'),
        'utilization': metrics.get('utilization_display'),
        'headroom': metrics.get('headroom_percent_display'),
        'capacity_posture': metrics.get('capacity_posture'),
    }


def _performance_payload(performance_metrics: dict[str, Any]) -> dict[str, Any]:
    existing = performance_metrics.get('performance')
    if isinstance(existing, dict) and existing:
        return existing
    return {
        'request_rate': performance_metrics.get('request_rate_display', 'N/A'),
        'error_ratio': performance_metrics.get('error_ratio_display', 'N/A'),
        'waiting': performance_metrics.get('waiting_display', 'N/A'),
        'offline_nodes': performance_metrics.get('offline_nodes_display', 'N/A'),
        'traffic': performance_metrics.get('traffic_total_bps_display', 'N/A'),
    }


def _risk_findings(metrics: dict[str, Any], alert_rows: list[Any]) -> list[dict[str, Any]]:
    return [
        *[item for item in (metrics.get('signals') or []) if isinstance(item, dict)],
        *[item for item in alert_rows if isinstance(item, dict)],
    ]


def _evidence_boundary(
    system: ObjectStorageSystem,
    overview: dict[str, Any],
    alerts: dict[str, Any],
) -> dict[str, Any]:
    metrics_source = _mapping(overview.get('metrics_source'))
    metrics_readiness = _mapping(overview.get('metrics_readiness'))
    forecast_materialization = _mapping(overview.get('forecast_materialization'))
    alert_source = _mapping(alerts.get('alert_source'))
    return {
        'inventory_source': 'Committed Object Storage inventory snapshot',
        'metrics_source': str(metrics_source.get('provider_label') or 'Metrics Source'),
        'inventory_cutoff': system.inventory_observed_at,
        'metrics_contract': str(metrics_readiness.get('label') or 'Unknown'),
        'forecast_state': str(forecast_materialization.get('label') or 'Unknown'),
        'alert_source': str(alert_source.get('resolved_label') or 'Unavailable'),
    }


def get_report_object_storage_analysis_payload(report: Report) -> dict[str, Any]:
    """Collect one governed Object Storage analytics snapshot for PDF/XLSX/CSV rendering."""

    validate_report_instance(report)
    system_id = require_object_storage_system(report)
    system = db.session.get(ObjectStorageSystem, system_id)
    if system is None:
        return {'_error': 'The selected Object Storage system no longer exists.'}

    args = MultiDict(
        [
            ('system_id', system_id),
            ('time_range', report.period or '30d'),
            ('history_window', '30d'),
            ('source', 'auto'),
        ]
    )
    overview = get_object_storage_analytics_context('overview', args)
    performance = get_object_storage_analytics_context('performance', args)
    alerts = get_object_storage_analytics_context('alerts', args)

    metrics = _mapping(overview.get('metrics'))
    performance_metrics = _mapping(performance.get('metrics'))
    alert_rows = _alert_rows(alerts)
    bucket_rows = list(metrics.get('bucket_rows') or [])
    evidence_boundary = _evidence_boundary(system, overview, alerts)
    now = datetime.now(UTC)

    return {
        'selected_system': {
            'id': system.id,
            'name': system.name,
            'environment': system.environment,
            'status': system.status,
        },
        'system': {
            'id': system.id,
            'name': system.name,
            'environment': system.environment,
            'status': system.status,
        },
        'summary': {
            'capacity': metrics.get('capacity_total_display', 'N/A'),
            'usage': metrics.get('usage_total_display', 'N/A'),
            'headroom': metrics.get('capacity_free_display', 'N/A'),
            'utilization': metrics.get('utilization_display', 'N/A'),
            'buckets': metrics.get('bucket_count_display', 'N/A'),
            'objects': metrics.get('object_count_display', 'N/A'),
        },
        'capacity_usage': _capacity_usage(metrics),
        'bucket_rows': bucket_rows,
        'bucket_analysis': metrics.get('bucket_analysis') or {},
        'performance': _performance_payload(performance_metrics),
        'forecast_display': metrics.get('forecast_display') or {},
        'forecast_materialization': overview.get('forecast_materialization') or {},
        'top_consumers': bucket_rows[:10],
        'signals': metrics.get('signals') or [],
        'risk_findings': _risk_findings(metrics, alert_rows),
        'signal_posture': metrics.get('signal_posture') or {},
        'operational_posture': metrics.get('operational_posture') or {},
        'alerts': alert_rows,
        'alert_posture': alerts.get('alert_posture') or {},
        'source_status': _source_status(overview),
        'metrics_source': overview.get('metrics_source') or {},
        'metrics_readiness': overview.get('metrics_readiness') or {},
        'evidence_boundary': evidence_boundary,
        'data_cutoff': system.inventory_observed_at or now,
        'generated_at': now,
    }
