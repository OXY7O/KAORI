from __future__ import annotations

from typing import Any

from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.analytics.workload.service import WorkloadAnalysisService
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_workload_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService

def get_report_workload_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Workload Analysis report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        workload_service = WorkloadAnalysisService(
            utilization_service,
        )

        prometheus_status = workload_service.get_prometheus_status()

        selected_namespace = report.namespace or ''
        selected_time_range = report.period or '24h'

        namespace_options = workload_service.get_all_namespace_options()

        tenant_quota_summary = workload_service.get_tenant_quota_summary(
            selected_namespace=selected_namespace,
        )

        tenant_quota_rows = tenant_quota_summary.get(
            'rows',
            [],
        )

        workload_mapping_payload = workload_service.get_workload_mapping_payload(
            selected_namespace=selected_namespace,
            time_range=selected_time_range,
        )

        workload_mapping_rows = workload_mapping_payload.get(
            'rows',
            [],
        )

        governance_findings = workload_service.get_governance_findings(
            tenant_quota_rows=tenant_quota_rows,
            workload_mapping_rows=workload_mapping_rows,
        )

        actionable_recommendations = build_workload_actionable_recommendations(
            {
                'tenant_quota_rows': tenant_quota_rows,
                'workload_mapping_rows': workload_mapping_rows,
                'governance_findings': governance_findings,
                'selected_namespace': selected_namespace or 'All Namespaces',
                'selected_time_range': selected_time_range,
            }
        )

        namespace_names = {
            str(row.get('namespace') or '').strip()
            for row in [*tenant_quota_rows, *workload_mapping_rows]
            if str(row.get('namespace') or '').strip()
        }
        pod_count = sum(
            _safe_non_negative_int(row.get('replicas'))
            for row in workload_mapping_rows
            if isinstance(row, dict)
        )
        response_time_ms = prometheus_status.get('response_time_ms')
        response_time_display = (
            f'{float(response_time_ms):.0f} ms'
            if isinstance(response_time_ms, (int, float))
            else str(prometheus_status.get('response_time_display') or 'Committed')
        )
        source_evidence = [
            {
                'source': 'Prometheus Workload Evidence',
                'freshness': response_time_display,
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Tenant Quota Analysis',
                'freshness': 'Committed' if tenant_quota_rows else 'Not Available',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Workload Resource Mapping',
                'freshness': 'Committed' if workload_mapping_rows else 'Not Available',
                'last_collected': 'At report cut-off',
            },
            {
                'source': 'Governance Recommendation Evidence',
                'freshness': 'Committed',
                'last_collected': 'At report cut-off',
            },
        ]

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
            'selected_namespace': selected_namespace or 'All Namespaces',
            'selected_time_range': selected_time_range,
            'prometheus_status': prometheus_status,
            'namespace_options': namespace_options,
            'tenant_quota_summary': tenant_quota_summary,
            'tenant_quota_rows': tenant_quota_rows,
            'workload_mapping_payload': workload_mapping_payload,
            'workload_mapping_rows': workload_mapping_rows,
            'governance_findings': governance_findings,
            'actionable_recommendations': actionable_recommendations,
            'inventory_summary': {
                'workload_count': len(workload_mapping_rows),
                'pod_count': pod_count,
                'namespace_count': len(namespace_names),
            },
            'source_evidence': source_evidence,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def _safe_non_negative_int(value: Any) -> int:
    try:
        return max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        return 0
