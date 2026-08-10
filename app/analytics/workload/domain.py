from __future__ import annotations

from typing import Any


def build_workload_posture(
    tenant_rows: list[dict[str, Any]],
    workload_rows: list[dict[str, Any]],
    governance_findings: list[dict[str, Any]],
) -> dict[str, str]:
    """Return an evidence-aware aggregate posture for the selected scope."""
    if not tenant_rows and not workload_rows:
        return {
            'value': 'Unknown',
            'description': 'No committed tenant quota or active workload evidence is available.',
            'tone': 'unknown',
            'icon': 'circle-help',
        }

    critical_count = sum(1 for item in governance_findings if item.get('severity') == 'critical')
    warning_count = sum(1 for item in governance_findings if item.get('severity') == 'warning')
    if critical_count:
        return {
            'value': 'Critical',
            'description': 'Critical quota or workload configuration findings need immediate review.',
            'tone': 'critical',
            'icon': 'shield-alert',
        }
    if warning_count:
        return {
            'value': 'Watch',
            'description': 'Review quota, request, limit, QoS, or right-sizing findings.',
            'tone': 'warning',
            'icon': 'triangle-alert',
        }

    quota_evidence_complete = bool(tenant_rows) and all(
        row.get('quota_status', {}).get('label') == 'Complete'
        and bool(row.get('quota_pressure_available'))
        and bool(row.get('runtime_demand_available'))
        for row in tenant_rows
    )
    workload_evidence_complete = bool(workload_rows) and all(
        row.get('request_coverage', {}).get('label') == 'Complete'
        and row.get('metrics_coverage', {}).get('label') == 'Complete'
        and row.get('risk', {}).get('label') != 'Unknown'
        for row in workload_rows
    )
    if not quota_evidence_complete or not workload_evidence_complete:
        return {
            'value': 'Limited Evidence',
            'description': 'One or more quota, runtime, request, or selected-window evidence domains are incomplete.',
            'tone': 'unknown',
            'icon': 'database-zap',
        }

    return {
        'value': 'Healthy',
        'description': 'Complete workload governance evidence has no actionable finding.',
        'tone': 'normal',
        'icon': 'circle-check',
    }


def build_governance_findings(
    tenant_quota_rows: list[dict[str, Any]],
    workload_mapping_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build factual findings without manufacturing a healthy placeholder row."""
    definitions = (
        (
            sum(1 for row in tenant_quota_rows if (row.get('quota_status') or {}).get('label') == 'Missing'),
            'Namespaces Without ResourceQuota',
            'warning',
            'triangle-alert',
            'missing-quota',
        ),
        (
            sum(
                1
                for row in workload_mapping_rows
                if (row.get('request_coverage') or {}).get('label') in {'Missing', 'Partial'}
            ),
            'Workloads With Incomplete Requests',
            'critical',
            'shield-alert',
            'missing-request',
        ),
        (
            sum(
                1
                for row in workload_mapping_rows
                if (row.get('limit_coverage') or {}).get('label') in {'Memory Limit Missing', 'Limits Unset', 'Partial'}
            ),
            'Workloads Need Memory Limit Review',
            'warning',
            'triangle-alert',
            'missing-limit',
        ),
        (
            sum(1 for row in workload_mapping_rows if (row.get('qos') or {}).get('label') == 'BestEffort'),
            'BestEffort Workloads',
            'warning',
            'info',
            'best-effort',
        ),
        (
            sum(1 for row in workload_mapping_rows if (row.get('metrics_coverage') or {}).get('label') != 'Complete'),
            'Workloads Have Incomplete Metrics Coverage',
            'unknown',
            'database-zap',
            'metrics-coverage',
        ),
        (
            sum(1 for row in workload_mapping_rows if 'reduce' in str(row.get('recommendation') or '').casefold()),
            'Workloads Need Right-Sizing Review',
            'warning',
            'scale',
            'right-sizing',
        ),
    )
    return [
        {
            'label': f'{count} {label}',
            'severity': severity,
            'icon': icon,
            'filter': filter_name,
        }
        for count, label, severity, icon, filter_name in definitions
        if count
    ]
