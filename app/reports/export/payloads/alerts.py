from __future__ import annotations

from typing import Any, cast

from app.analytics.kubernetes.alerts.application import present_alerts_materialized_context
from app.analytics.kubernetes.alerts.contracts import AlertSourceStatus, AlertsSelection
from app.analytics.kubernetes.alerts.health import build_summary, is_alert_evidence_complete
from app.analytics.kubernetes.alerts.signals import build_selected_cluster_signal_overview
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_alerts_actionable_recommendations
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_alerts_anomalies_payload(report: Report) -> dict[str, Any]:
    """Build the report from the committed ``analytics.alerts`` snapshot.

    Report rendering must not call Alertmanager or Prometheus directly. Missing or
    expired committed evidence is represented explicitly so the PDF can still be
    generated without presenting synthetic zeroes as healthy observations.
    """

    cluster = None
    try:
        cluster = get_report_selected_cluster(report)
        cluster_id = str(getattr(cluster, 'id', ''))
        context, snapshot_collected_at = _read_committed_context(cluster_id=cluster_id)
        selected_namespace = report.namespace or ''

        if context:
            presented = present_alerts_materialized_context(
                context,
                AlertsSelection(
                    namespace=selected_namespace,
                    alerts_per_page=50,
                    preserve_namespace=True,
                    anomalies_per_page=50,
                ),
            )
            alerts = list(presented.get('filtered_alerts') or [])
            anomalies = list(presented.get('filtered_anomalies') or [])
            source_status = cast(AlertSourceStatus, presented.get('source_status') or {})
            summary = build_summary(
                alerts=alerts,
                anomalies=anomalies,
                source_status=source_status,
            )
            signal_overview = build_selected_cluster_signal_overview(
                cluster=presented.get('selected_cluster'),
                alerts=alerts,
                anomalies=anomalies,
                source_status=source_status,
                evidence_complete=is_alert_evidence_complete(
                    source_status=source_status,
                    anomaly_source_status=presented.get('anomaly_source_status') or {},
                ),
            )
            actionable_recommendations = build_alerts_actionable_recommendations(
                {
                    'alerts': alerts,
                    'all_alerts': alerts,
                    'anomalies': anomalies,
                    'all_anomalies': anomalies,
                    'summary': summary,
                    'source_status': source_status,
                    'collection_warnings': list(presented.get('collection_warnings') or []),
                    'anomaly_source_status': presented.get('anomaly_source_status') or {},
                    'selected_cluster_signal_overview': signal_overview,
                }
            )
        else:
            presented = _unavailable_context(selected_namespace=selected_namespace)
            alerts = []
            anomalies = []
            summary = presented['summary']
            signal_overview = presented['selected_cluster_signal_overview']
            actionable_recommendations = []

        return {
            'cluster': {
                'id': cluster_id,
                'name': str(getattr(cluster, 'name', 'Unknown Cluster')),
                'environment': get_environment_label(
                    getattr(cluster, 'environment', None),
                    empty='',
                ),
                'status': str(getattr(cluster, 'status', '') or ''),
            },
            'selected_namespace': selected_namespace or 'All Namespaces',
            'selected_source': presented.get('selected_source', 'auto'),
            'selected_severity': 'all',
            'selected_status': 'all',
            'source_status': presented.get('source_status', {}),
            'anomaly_source_status': presented.get('anomaly_source_status', {}),
            'collection_warnings': presented.get('collection_warnings', []),
            'integration_status': presented.get('integration_status', {}),
            'resource_links': presented.get('resource_links', {}),
            'summary': summary,
            'alerts': alerts,
            'anomalies': anomalies,
            'selected_cluster_signal_overview': signal_overview,
            'source_health': presented.get('source_health', {}),
            'routing_summary': presented.get('routing_summary', {}),
            'silence_summary': presented.get('silence_summary', {}),
            'inhibition_summary': presented.get('inhibition_summary', {}),
            'ownership_summary': presented.get('ownership_summary', {}),
            'incident_readiness': presented.get('incident_readiness', {}),
            'actionable_recommendations': actionable_recommendations,
            'recommendations': actionable_recommendations,
            'generated_at': presented.get('generated_at') or snapshot_collected_at,
            'namespace_options': presented.get('namespace_options', []),
            'committed_evidence_available': bool(context),
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)


def _read_committed_context(*, cluster_id: str) -> tuple[dict[str, Any], Any]:
    from app.analytics.kubernetes.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.alerts',
        parameters={'cluster_id': cluster_id, 'source': 'auto'},
    )
    context = result.context or {}
    if not isinstance(context, dict):
        return {}, None
    return context, getattr(getattr(result, 'snapshot', None), 'generated_at', None)


def _unavailable_context(*, selected_namespace: str) -> dict[str, Any]:
    return {
        'selected_source': 'auto',
        'selected_namespace': selected_namespace,
        'source_status': {
            'source': 'none',
            'selected_source': 'auto',
            'resolved_source': 'none',
            'label': 'Committed Alert Evidence Unavailable',
            'configured': False,
            'connected': False,
            'fallback_used': False,
            'fallback_reason': None,
            'error': 'No current committed analytics.alerts snapshot is available.',
            'response_time_ms': None,
            'last_checked_at': None,
        },
        'anomaly_source_status': {
            'configured': False,
            'connected': False,
            'label': 'Committed Anomaly Evidence Unavailable',
            'error': 'No current committed analytics.alerts snapshot is available.',
            'response_time_ms': None,
            'partial': True,
            'available_queries': [],
            'failed_queries': ['restart', 'readiness'],
        },
        'collection_warnings': [
            {
                'title': 'Committed Alert Evidence Is Unavailable',
                'detail': 'The report worker could not read a current analytics.alerts snapshot.',
                'remediation': 'Run or wait for the Analytics materialization worker before regenerating the report.',
            }
        ],
        'summary': {
            'active_alerts': None,
            'critical_alerts': None,
            'warning_alerts': None,
            'detected_anomalies': None,
            'source_connected': False,
        },
        'selected_cluster_signal_overview': {
            'priority': {
                'level': 'unknown',
                'label': 'Unknown',
                'description': 'Committed alert and anomaly evidence is unavailable.',
                'icon': 'circle-help',
            }
        },
        'namespace_options': [],
        'generated_at': None,
    }
