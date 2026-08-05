from __future__ import annotations

from typing import Any

from app.analytics.alerts.application import get_alerts_context
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_alerts_actionable_recommendations
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error

def get_report_alerts_anomalies_payload(
    report: Report,
) -> dict[str, Any]:
    cluster = None
    try:
        cluster = get_report_selected_cluster(report)
        context = get_alerts_context(
            cluster_id=cluster.id,
            source='auto',
            severity='all',
            status='all',
            namespace=report.namespace or '',
            search='',
            page=1,
            alerts_per_page=50,
            anomalies_per_page=50,
        )


        actionable_recommendations = build_alerts_actionable_recommendations(
            {
                'alerts': context.get(
                    'all_alerts',
                    context.get(
                        'alerts',
                        [],
                    ),
                ),
                'all_alerts': context.get(
                    'all_alerts',
                    context.get(
                        'alerts',
                        [],
                    ),
                ),
                'anomalies': context.get(
                    'all_anomalies',
                    context.get(
                        'anomalies',
                        [],
                    ),
                ),
                'all_anomalies': context.get(
                    'all_anomalies',
                    context.get(
                        'anomalies',
                        [],
                    ),
                ),
                'summary': context.get(
                    'summary',
                    {},
                ),
                'source_status': context.get(
                    'source_status',
                    {},
                ),
                'selected_cluster_signal_overview': context.get(
                    'selected_cluster_signal_overview',
                    {},
                ),
            }
        )

        return {
            'cluster': {
                'id': str(
                    getattr(
                        cluster,
                        'id',
                        '',
                    )
                ),
                'name': str(
                    getattr(
                        cluster,
                        'name',
                        'Unknown Cluster',
                    )
                ),
                'environment': get_environment_label(getattr(cluster, 'environment', None), empty=''),
                'status': str(
                    getattr(
                        cluster,
                        'status',
                        '',
                    )
                    or ''
                ),
            },
            'selected_namespace': context.get(
                'selected_namespace',
                report.namespace or 'All Namespaces',
            )
            or 'All Namespaces',
            'selected_source': context.get(
                'selected_source',
                'auto',
            ),
            'selected_severity': context.get(
                'selected_severity',
                'all',
            ),
            'selected_status': context.get(
                'selected_status',
                'all',
            ),
            'source_status': context.get(
                'source_status',
                {},
            ),
            'integration_status': context.get(
                'integration_status',
                {},
            ),
            'resource_links': context.get(
                'resource_links',
                {},
            ),
            'summary': context.get(
                'summary',
                {},
            ),
            'alerts': context.get(
                'all_alerts',
                context.get(
                    'alerts',
                    [],
                ),
            ),
            'anomalies': context.get(
                'all_anomalies',
                context.get(
                    'anomalies',
                    [],
                ),
            ),
            'selected_cluster_signal_overview': context.get(
                'selected_cluster_signal_overview',
                {},
            ),
            'source_health': context.get(
                'source_health',
                {},
            ),
            'routing_summary': context.get(
                'routing_summary',
                {},
            ),
            'silence_summary': context.get(
                'silence_summary',
                {},
            ),
            'inhibition_summary': context.get(
                'inhibition_summary',
                {},
            ),
            'ownership_summary': context.get(
                'ownership_summary',
                {},
            ),
            'incident_readiness': context.get(
                'incident_readiness',
                {},
            ),
            'actionable_recommendations': actionable_recommendations,
            'recommendations': actionable_recommendations,
            'generated_at': context.get(
                'generated_at',
            ),
            'namespace_options': context.get(
                'namespace_options',
                [],
            ),
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)
