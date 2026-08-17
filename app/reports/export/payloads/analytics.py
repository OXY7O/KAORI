from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.extensions.db import db
from app.kubernetes.analytics.overview.service import get_analytics_overview
from app.models.report import Report, ReportSchedule
from app.reports.catalog import require_selected_cluster
from app.reports.export.payloads.alerts import get_report_alerts_anomalies_payload
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_analytics_overview_payload(
    report: Report,
) -> dict[str, Any]:
    cluster = None
    try:
        selected_cluster_id = str(get_report_selected_cluster(report).id)
        time_range = report.period or '24h'

        payload = get_analytics_overview(
            selected_cluster_id=selected_cluster_id,
            time_range=time_range,
            hydrate_snapshot_sections=True,
        )
        payload['alert_detail'] = _collect_alert_detail(report)
        payload['reporting_summary'] = _collect_reporting_summary(report)
        payload['inventory_snapshot'] = _collect_inventory_snapshot(report)
        payload['data_freshness'] = _collect_data_freshness(payload)
        return payload
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)


def _collect_alert_detail(report: Report) -> dict[str, Any]:
    detail = get_report_alerts_anomalies_payload(report)
    if detail.get('_error'):
        return {}
    return detail


def _collect_reporting_summary(report: Report) -> dict[str, Any]:
    try:
        from app.reports.overview.service import get_storage_context, serialize_recent_report

        cluster_id = require_selected_cluster(report)
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def count_reports(*statuses: str, since: datetime | None = None) -> int:
            statement = select(func.count(Report.id)).where(Report.cluster_id == cluster_id)
            if statuses:
                statement = statement.where(Report.status.in_(statuses))
            if since is not None:
                statement = statement.where(Report.created_at >= since)
            return int(db.session.scalar(statement) or 0)

        recent_reports = db.session.scalars(
            select(Report).where(Report.cluster_id == cluster_id).order_by(Report.created_at.desc()).limit(8)
        ).all()
        schedules = db.session.scalars(
            select(ReportSchedule)
            .where(ReportSchedule.cluster_id == cluster_id)
            .order_by(ReportSchedule.is_enabled.desc(), ReportSchedule.next_run_at.asc())
            .limit(8)
        ).all()
        active_schedules = int(
            db.session.scalar(
                select(func.count(ReportSchedule.id)).where(
                    ReportSchedule.cluster_id == cluster_id,
                    ReportSchedule.is_enabled.is_(True),
                )
            )
            or 0
        )
        schedule_count = int(
            db.session.scalar(select(func.count(ReportSchedule.id)).where(ReportSchedule.cluster_id == cluster_id)) or 0
        )

        return {
            'counts': {
                'total': count_reports(),
                'ready': count_reports('ready'),
                'pending': count_reports('requested', 'generating'),
                'failed': count_reports('failed'),
                'archived': count_reports('archived'),
                'generated_this_month': count_reports(since=month_start),
                'schedules': schedule_count,
                'active_schedules': active_schedules,
            },
            'recent_reports': [serialize_recent_report(item) for item in recent_reports],
            'schedules': [_serialize_schedule(schedule) for schedule in schedules],
            'storage': _serialize_storage_context(get_storage_context()),
            'notes': [
                'Analytics artifacts use one selected-cluster source boundary for PDF and CSV.',
                'Recurring schedules and generated records shown here are filtered to the selected cluster.',
            ],
        }
    except Exception:
        return {
            'counts': {},
            'recent_reports': [],
            'schedules': [],
            'storage': {},
            'notes': ['Selected-cluster reporting operation evidence was unavailable during payload collection.'],
        }


def _serialize_schedule(schedule: ReportSchedule) -> dict[str, Any]:
    return {
        'name': schedule.name,
        'cadence': schedule.cadence,
        'next_run_at': _format_datetime(schedule.next_run_at),
        'last_run_at': _format_datetime(schedule.last_run_at),
        'last_status': schedule.last_status or 'Not Run',
        'is_enabled': bool(schedule.is_enabled),
    }


def _serialize_storage_context(storage: dict[str, Any]) -> dict[str, Any]:
    return {
        'backend': storage.get('backend_label') or storage.get('backend') or 'Not Available',
        'status': storage.get('display_status') or storage.get('status') or 'Not Available',
        'tone': storage.get('tone') or storage.get('status_tone') or 'unknown',
        'description': storage.get('description') or storage.get('guidance') or '',
    }


def _collect_inventory_snapshot(report: Report) -> dict[str, Any]:
    try:
        from app.kubernetes.inventory.overview import get_inventory_overview

        cluster_id = require_selected_cluster(report)
        overview = get_inventory_overview()
        selected = next(
            (item for item in overview.get('clusters', []) if str(item.get('id')) == cluster_id),
            None,
        )
        if selected is None:
            return {'clusters': [], 'health': {}, 'posture': {'status': 'Unknown', 'tone': 'unknown'}}

        counts = dict(selected.get('counts') or {})
        synced_at = selected.get('synced_at')
        fresh = selected.get('sync_status_tone') == 'normal'
        connected = selected.get('status') == 'connected'
        totals = {
            'total_clusters': 1,
            **{f'total_{key}': int(value or 0) for key, value in counts.items()},
        }
        return {
            **totals,
            'inventory_total': sum(int(value or 0) for value in counts.values()),
            'active_signal_count': len(selected.get('signals') or []),
            'clusters': [selected],
            'inventory_summary': {cluster_id: overview.get('inventory_summary', {}).get(cluster_id, {})},
            'health': {
                'connected_clusters': 1 if connected else 0,
                'healthy_clusters': 1 if connected and fresh else 0,
                'never_synced': 1 if synced_at is None else 0,
                'stale_synced': 1 if synced_at is not None and not fresh else 0,
                'fresh_synced': 1 if fresh else 0,
                'synced_clusters': 1 if synced_at is not None else 0,
                'disconnected_clusters': 0 if connected else 1,
                'coverage_score': 100 if synced_at is not None else 0,
                'connection_score': 100 if connected else 0,
                'freshness_score': 100 if fresh else 0,
                'freshness_window_hours': selected.get('freshness_window_hours'),
                'last_sync': synced_at,
            },
            'posture': {
                'status': 'Healthy' if connected and fresh else 'Attention',
                'tone': 'normal' if connected and fresh else 'warning',
            },
        }
    except Exception:
        return {
            'clusters': [],
            'health': {},
            'posture': {'status': 'Unknown', 'tone': 'unknown'},
        }


def _collect_data_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = payload.get('snapshot_summary') or {}
    metrics_source = payload.get('metrics_source') or {}
    alert_detail = payload.get('alert_detail') or {}
    inventory = payload.get('inventory_snapshot') or {}
    inventory_health = inventory.get('health') or {}

    sources = [
        {
            'label': 'Metrics',
            'source': 'Metrics Source Observation Cache',
            'type': 'Metrics Cache',
            'last_successful': metrics_source.get('last_checked_at') or 'Not Available',
            'freshness': _format_latency(metrics_source.get('response_time_ms')),
            'status': metrics_source.get('status_label') or metrics_source.get('status') or 'Unknown',
            'tone': metrics_source.get('status_tone') or metrics_source.get('status') or 'unknown',
        },
        {
            'label': 'Inventory',
            'source': 'Kubernetes Committed Inventory',
            'type': 'Committed Snapshot',
            'last_successful': _format_datetime(inventory_health.get('last_sync')),
            'freshness': _format_score(inventory_health.get('freshness_score')),
            'status': 'Current' if inventory_health.get('fresh_synced') else 'Attention',
            'tone': 'normal' if inventory_health.get('fresh_synced') else 'warning',
        },
        {
            'label': 'Analytics',
            'source': 'Analytics Materialized Snapshots',
            'type': 'Committed Analytics',
            'last_successful': snapshot.get('latest_generated_at') or 'Not Available',
            'freshness': snapshot.get('analysis_window') or 'Not Available',
            'status': snapshot.get('status') or 'Unknown',
            'tone': snapshot.get('tone') or 'unknown',
        },
        {
            'label': 'Alerts',
            'source': 'Alertmanager Observation Cache',
            'type': 'Alert Cache',
            'last_successful': alert_detail.get('generated_at') or 'Not Available',
            'freshness': 'At report cut-off',
            'status': _source_status_label(alert_detail.get('source_status')),
            'tone': _source_status_tone(alert_detail.get('source_status')),
        },
    ]

    expected = int(snapshot.get('expected_dataset_count') or 0)
    current = int(snapshot.get('current_dataset_count') or 0)
    failed = int(snapshot.get('failed_dataset_count') or 0)
    issues: list[dict[str, Any]] = []
    if expected > current:
        issues.append(
            {
                'issue_type': 'Incomplete Analytics Dataset Coverage',
                'source': 'Analytics Materialization',
                'count': expected - current,
                'impact': 'Medium',
                'status': 'Open',
            }
        )
    if failed:
        issues.append(
            {
                'issue_type': 'Failed Analytics Dataset',
                'source': 'Analytics Materialization',
                'count': failed,
                'impact': 'High',
                'status': 'Open',
            }
        )

    return {
        'sources': sources,
        'issues': issues,
        'average_latency': _format_latency(metrics_source.get('response_time_ms')),
        'retention_coverage': 'Policy Managed',
    }


def _source_status_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get('label') or value.get('status_label') or value.get('status') or 'Unknown')
    return str(value or 'Unknown')


def _source_status_tone(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get('tone') or value.get('status_tone') or value.get('status') or 'unknown')
    return str(value or 'unknown')


def _format_datetime(value: Any) -> str:
    if not isinstance(value, datetime):
        return str(value or 'Not Available')
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).strftime('%d/%m/%Y %H:%M UTC')


def _format_latency(value: Any) -> str:
    try:
        latency = float(value)
    except (TypeError, ValueError):
        return 'Not Available'
    return f'{latency:.0f} ms'


def _format_score(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 'Not Available'
    return f'{score:.0f}%'
