from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.analytics.overview.service import get_analytics_overview
from app.extensions.db import db
from app.models.report import Report, ReportSchedule
from app.reports.export.payloads.alerts import get_report_alerts_anomalies_payload


def get_report_analytics_overview_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        selected_cluster_id = report.cluster_id or None
        time_range = report.period or '24h'

        payload = get_analytics_overview(
            selected_cluster_id=selected_cluster_id,
            time_range=time_range,
            hydrate_snapshot_sections=True,
        )
        payload['alert_detail'] = _collect_alert_detail(report)
        payload['reporting_summary'] = _collect_reporting_summary()
        payload['inventory_snapshot'] = _collect_inventory_snapshot()
        payload['data_freshness'] = _collect_data_freshness(payload)
        return payload
    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def _collect_alert_detail(report: Report) -> dict[str, Any]:
    detail = get_report_alerts_anomalies_payload(report)
    if detail.get('_error'):
        return {}
    return detail


def _collect_reporting_summary() -> dict[str, Any]:
    try:
        from app.reports.overview.service import (
            get_recent_reports,
            get_report_counts,
            get_storage_context,
        )

        schedules = db.session.scalars(
            select(ReportSchedule)
            .order_by(ReportSchedule.is_enabled.desc(), ReportSchedule.next_run_at.asc())
            .limit(8)
        ).all()
        return {
            'counts': get_report_counts(),
            'recent_reports': get_recent_reports(limit=8),
            'schedules': [_serialize_schedule(schedule) for schedule in schedules],
            'storage': _serialize_storage_context(get_storage_context()),
            'notes': [
                'All generated PDF artifacts use the canonical KAORI WeasyPrint renderer.',
                'Recurring schedules remain governed independently from generated report records.',
            ],
        }
    except Exception:
        return {
            'counts': {},
            'recent_reports': [],
            'schedules': [],
            'storage': {},
            'notes': ['Reporting operation evidence was unavailable during payload collection.'],
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


def _collect_inventory_snapshot() -> dict[str, Any]:
    try:
        from app.inventory.overview import get_inventory_overview

        return get_inventory_overview()
    except Exception:
        return {
            'clusters': [],
            'health': {},
        }


def _collect_data_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = payload.get('snapshot_summary') or {}
    prometheus = payload.get('prometheus') or {}
    alert_detail = payload.get('alert_detail') or {}
    inventory = payload.get('inventory_snapshot') or {}
    inventory_health = inventory.get('health') or {}

    sources = [
        {
            'label': 'Metrics',
            'source': 'Prometheus Observation Cache',
            'type': 'Metrics Cache',
            'last_successful': prometheus.get('last_checked_at') or 'Not Available',
            'freshness': _format_latency(prometheus.get('response_time_ms')),
            'status': prometheus.get('status_label') or prometheus.get('status') or 'Unknown',
            'tone': prometheus.get('status_tone') or prometheus.get('status') or 'unknown',
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
        'average_latency': _format_latency(prometheus.get('response_time_ms')),
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
