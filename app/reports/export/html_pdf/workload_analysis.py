from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)
from app.reports.export.html_pdf.publication_copy import compact_governance_signal


def build_workload_analysis_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    cluster = _mapping(payload.get('cluster'))
    quota_summary = _mapping(payload.get('tenant_quota_summary'))
    quota_rows = _rows(payload.get('tenant_quota_rows') or quota_summary.get('rows'))
    mapping_payload = _mapping(payload.get('workload_mapping_payload'))
    mapping_rows = _rows(payload.get('workload_mapping_rows') or mapping_payload.get('rows'))
    governance_findings = _rows(payload.get('governance_findings'))
    actionable_recommendations = _rows(payload.get('actionable_recommendations'))

    inventory = _inventory_summary(payload, quota_rows, mapping_rows)
    quota = _quota_analysis(quota_summary, quota_rows)
    mapping = _mapping_analysis(mapping_payload, mapping_rows)
    configuration = _configuration_analysis(mapping_payload, mapping_rows)
    governance = _governance_analysis(governance_findings, mapping_rows, quota_rows)
    recommendations = _recommendation_plan(
        actionable_recommendations,
        governance,
        quota,
        configuration,
    )
    sources = _source_rows(payload, quota, mapping)

    findings = _executive_findings(quota, configuration, governance)
    environment = _text(cluster.get('environment'), 'Unknown')

    return {
        'presentation_version': 'v3.0-workload-analysis-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': 9,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': report_id,
        'report_name': report_name,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': environment,
            'purpose': (
                'Support application and platform review of workload inventory, tenant quota posture, '
                'resource configuration, QoS, right-sizing evidence, runtime risk, and accountable remediation.'
            ),
            'context': (
                'Quota, workload mapping, requests, limits, QoS, runtime metrics, and ownership remain separate '
                'evidence boundaries. Missing fields are never interpreted as compliant or as zero usage.'
            ),
        },
        'executive': {
            'metrics': (
                _metric('Workloads', inventory['workload_display'], inventory['status'], inventory['tone']),
                _metric('Pods', inventory['pod_display'], inventory['status'], inventory['tone']),
                _metric('Namespaces', inventory['namespace_display'], inventory['status'], inventory['tone']),
                _metric(
                    'Actionable Findings',
                    str(governance['actionable_count']),
                    'Requires Review' if governance['actionable_count'] else 'Clear',
                    'warning' if governance['actionable_count'] else 'normal',
                ),
            ),
            'inventory': inventory,
            'quota': quota,
            'configuration': configuration,
            'interpretation_title': _executive_title(quota, configuration, governance),
            'interpretation_body': _executive_body(inventory, quota, configuration, governance),
            'interpretation_note': (
                'Runtime health, resource governance, and application ownership must be validated independently.'
            ),
            'findings': findings,
        },
        'inventory': {
            'metrics': (
                _metric('Workloads', inventory['workload_display'], inventory['status'], inventory['tone']),
                _metric('Pods', inventory['pod_display'], inventory['status'], inventory['tone']),
                _metric('Namespaces', inventory['namespace_display'], inventory['status'], inventory['tone']),
                _metric('Inventory Coverage', inventory['coverage_display'], inventory['status'], inventory['tone']),
            ),
            'summary': inventory,
            'signals': governance['signals'][:3],
            'register': _inventory_register(inventory, governance),
            'decision': (
                'Use workload and namespace scope to assign triage. Runtime findings do not prove quota, request, '
                'limit, QoS, or right-sizing compliance.'
            ),
        },
        'quota': quota,
        'mapping': mapping,
        'configuration': configuration,
        'governance': governance,
        'recommendations': recommendations,
        'methodology': {
            'metrics': (
                _metric(
                    'Data Sources',
                    str(len(sources)),
                    'Active' if sources else 'Not Available',
                    'normal' if sources else 'warning',
                ),
                _metric(
                    'Workload Scope',
                    inventory['workload_display'],
                    'Committed' if inventory['available'] else 'Not Available',
                    inventory['tone'],
                ),
                _metric('Quota Scope', quota['coverage_display'], quota['status'], quota['tone']),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ),
            'sources': sources,
            'rules': (
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Quota Coverage', 'setting': 'Complete + Partial rows'},
                {'ref': 'M4', 'rule': 'Configuration Basis', 'setting': 'Requests, limits, QoS'},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ),
            'references': (
                _reference('M3', 'Quota Coverage', 'Coverage is derived only from committed namespace quota rows.'),
                _reference(
                    'M4',
                    'Configuration Basis',
                    'Workload configuration uses committed requests, limits, QoS, and metrics coverage.',
                ),
                _reference(
                    'M5',
                    'Missing Evidence',
                    'Unavailable evidence remains explicit and is never converted to compliant or zero.',
                ),
            ),
            'included': (
                'Committed workload, pod, and namespace scope derived from workload analysis rows.',
                'Committed ResourceQuota, request, limit, QoS, metrics coverage, and governance findings when available.',
                'Actionable recommendations generated from the committed workload payload.',
            ),
            'excluded': (
                'Live cluster state after the report cut-off.',
                'Application-owner identity when it is not committed in the source payload.',
                'Configuration changes, maintenance windows, and rollout approval not represented by evidence.',
            ),
            'limitations': (
                'Workload and pod counts inherit the selected Metrics Source and report scope.',
                'Quota absence and quota collection failure require separate operational validation.',
                'Validate every recommendation against live state before remediation.',
            ),
            'status_language': (
                _reference('S1', 'Not Available', 'No evidence exists for the requested dimension.'),
                _reference('S2', 'Not Collected', 'Collection was prevented by configuration or failure.'),
                _reference('S3', 'Partial Coverage', 'Evidence exists but does not cover the full requested scope.'),
                _reference(
                    'S4', 'Source Unavailable', 'The source was unreachable or not providing data at the cut-off.'
                ),
            ),
        },
    }


def _inventory_summary(
    payload: Mapping[str, Any],
    quota_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    workload_count = len(mapping_rows)
    pod_count = sum(max(_int(row.get('replicas')), 0) for row in mapping_rows)
    namespaces = {
        _text(row.get('namespace'), '') for row in [*quota_rows, *mapping_rows] if _text(row.get('namespace'), '')
    }
    namespace_options = payload.get('namespace_options')
    if not namespaces and isinstance(namespace_options, Sequence) and not isinstance(namespace_options, (str, bytes)):
        namespaces = {_text(item, '') for item in namespace_options if _text(item, '')}

    available = bool(mapping_rows or quota_rows)
    namespace_count = len(namespaces)
    coverage = 100.0 if mapping_rows else 0.0
    return {
        'available': available,
        'workload_count': workload_count,
        'pod_count': pod_count,
        'namespace_count': namespace_count,
        'cluster_count': 1 if _mapping(payload.get('cluster')) else 0,
        'workload_display': str(workload_count) if mapping_rows else 'Not Available',
        'pod_display': str(pod_count) if mapping_rows else 'Not Available',
        'namespace_display': str(namespace_count) if namespace_count else 'Not Available',
        'coverage': coverage,
        'coverage_display': f'{coverage:.0f}%' if available else 'Not Available',
        'status': 'Current' if available else 'Not Available',
        'tone': 'normal' if available else 'warning',
    }


def _quota_analysis(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = _int(summary.get('scope_total')) or len(rows)
    covered = _int(summary.get('scope_covered'))
    if not covered:
        covered = sum(1 for row in rows if _label(row.get('quota_status')) in {'Complete', 'Partial'})
    complete = sum(1 for row in rows if _label(row.get('quota_status')) == 'Complete')
    partial = sum(1 for row in rows if _label(row.get('quota_status')) == 'Partial')
    missing = sum(1 for row in rows if _label(row.get('quota_status')) == 'Missing')
    near_limit = _int(summary.get('scope_near_limit_count')) or sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and _float(row.get('quota_usage_percent')) >= 75
    )
    over_quota = sum(
        1 for row in rows if bool(row.get('quota_pressure_available')) and _float(row.get('quota_usage_percent')) >= 100
    )
    coverage = _percent(covered, total) if total else None
    available = bool(rows)
    status = 'Current' if available and missing == 0 else 'Review' if available else 'Not Available'
    tone = 'normal' if available and missing == 0 and over_quota == 0 else 'warning'

    records = []
    for index, row in enumerate(rows[:5], start=1):
        namespace = _text(row.get('namespace'), '-')
        status_label = _label(row.get('quota_status'), 'Unknown')
        risk = _label(row.get('risk'), 'Unknown')
        pressure = (
            _percent_display(row.get('quota_usage_percent'))
            if bool(row.get('quota_pressure_available'))
            else 'Not Available'
        )
        records.append(
            {
                'ref': f'Q{index}',
                'namespace': namespace,
                'coverage': status_label,
                'pressure': pressure,
                'risk': risk,
                'tone': _tone(risk),
            }
        )

    return {
        'available': available,
        'total': total,
        'covered': covered,
        'complete': complete,
        'partial': partial,
        'missing': missing,
        'near_limit': near_limit,
        'over_quota': over_quota,
        'coverage': coverage,
        'coverage_display': _percent_display(coverage) if coverage is not None else 'Not Available',
        'status': status,
        'tone': tone,
        'metrics': (
            _metric(
                'Namespaces',
                str(total) if total else 'Not Available',
                'Committed Scope' if total else 'Not Available',
                'normal' if total else 'warning',
            ),
            _metric(
                'Quota Coverage', _percent_display(coverage) if coverage is not None else 'Not Available', status, tone
            ),
            _metric(
                'Missing Quota',
                str(missing) if available else 'Not Available',
                'Review' if missing else 'Clear' if available else 'Not Available',
                'warning' if missing or not available else 'normal',
            ),
            _metric(
                'Near / Over Limit',
                str(near_limit),
                'Review' if near_limit else 'Clear',
                'warning' if near_limit else 'normal',
            ),
        ),
        'records': records,
        'requirements': (
            {
                'ref': 'QE1',
                'evidence': 'ResourceQuota Inventory',
                'definition': 'Quota object and namespace scope',
                'status': 'Current' if available else 'Missing',
                'action': 'Monitor' if available else 'Required',
            },
            {
                'ref': 'QE2',
                'evidence': 'Quota Used / Hard',
                'definition': 'Used and hard values by resource',
                'status': 'Current' if available else 'Missing',
                'action': 'Review' if near_limit else 'Monitor' if available else 'Required',
            },
            {
                'ref': 'QE3',
                'evidence': 'LimitRange Inventory',
                'definition': 'Default and min/max controls',
                'status': 'Not Collected',
                'action': 'Required',
            },
            {
                'ref': 'QE4',
                'evidence': 'Enforcement Result',
                'definition': 'Quota rejection or policy evidence',
                'status': 'Not Collected',
                'action': 'Validate',
            },
        ),
        'decision': (
            'Review namespaces with missing or partial quota definitions before approving additional workload growth.'
            if available
            else 'Restore ResourceQuota evidence before assigning tenant governance status.'
        ),
    }


def _mapping_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    namespace_count = len({_text(row.get('namespace'), '') for row in rows if _text(row.get('namespace'), '')})
    complete_requests = sum(1 for row in rows if _label(row.get('request_coverage')) == 'Complete')
    complete_limits = sum(1 for row in rows if _label(row.get('limit_coverage')) == 'Complete')
    complete_metrics = sum(1 for row in rows if _label(row.get('metrics_coverage')) == 'Complete')
    high_risk = sum(1 for row in rows if _label(row.get('risk')) in {'High', 'Critical'})
    available = bool(rows)

    records = []
    for index, row in enumerate(rows[:5], start=1):
        records.append(
            {
                'ref': f'M{index}',
                'workload': _text(row.get('workload'), '-'),
                'type': _text(row.get('type'), '-'),
                'namespace': _text(row.get('namespace'), '-'),
                'mapping': f'{_int(row.get("replicas"))} pod(s)'
                if row.get('replicas') is not None
                else 'Inventory row',
                'status': _label(row.get('risk'), 'Unknown'),
                'tone': _tone(_label(row.get('risk'), 'Unknown')),
            }
        )

    return {
        'available': available,
        'metrics': (
            _metric(
                'Workloads',
                str(total) if available else 'Not Available',
                'Inventory Available' if available else 'Not Available',
                'normal' if available else 'warning',
            ),
            _metric(
                'Namespaces',
                str(namespace_count) if namespace_count else 'Not Available',
                'Committed Scope' if namespace_count else 'Not Available',
                'normal' if namespace_count else 'warning',
            ),
            _metric(
                'Resource Mapping',
                _percent_display(_percent(complete_metrics, total)) if total else 'Not Available',
                'Complete Metrics' if total else 'Not Available',
                'normal' if total and complete_metrics == total else 'warning',
            ),
            _metric('Owner Mapping', 'Not Available', 'Not Committed', 'warning'),
        ),
        'records': records,
        'identities': tuple(
            {
                'ref': item['ref'],
                'title': item['workload'],
                'metadata': f'Namespace: {item["namespace"]} · Type: {item["type"]}',
            }
            for item in records
        ),
        'coverage': (
            {
                'label': 'Inventory to Namespace',
                'value': 100.0 if available else 0.0,
                'display': 'Available' if available else 'Not Available',
                'available': available,
            },
            {
                'label': 'Requests Coverage',
                'value': _percent(complete_requests, total) or 0.0,
                'display': _percent_display(_percent(complete_requests, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Limits Coverage',
                'value': _percent(complete_limits, total) or 0.0,
                'display': _percent_display(_percent(complete_limits, total)) if total else 'Not Available',
                'available': available,
            },
            {'label': 'Application Owner', 'value': 0.0, 'display': 'Not Available', 'available': False},
        ),
        'interpretation_title': (
            'Mapping supports workload triage, but ownership remains incomplete.'
            if available
            else 'Workload mapping evidence is not available.'
        ),
        'interpretation_body': (
            f'{total} workload row(s) cover {namespace_count} namespace(s). '
            f'{high_risk} high-risk workload row(s) require review. Application-owner identity is not committed.'
            if available
            else 'Restore committed workload-to-pod and namespace mapping before deriving configuration posture.'
        ),
        'decision': (
            'Confirm controller, application owner, deployment intent, maintenance window, and rollback readiness before changing resources or replicas.'
        ),
    }


def _configuration_analysis(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    request_complete = sum(1 for row in rows if _label(row.get('request_coverage')) == 'Complete')
    limit_complete = sum(1 for row in rows if _label(row.get('limit_coverage')) == 'Complete')
    metrics_complete = sum(1 for row in rows if _label(row.get('metrics_coverage')) == 'Complete')
    best_effort = sum(1 for row in rows if _label(row.get('qos')) == 'BestEffort')
    missing_requests = sum(1 for row in rows if _label(row.get('request_coverage')) in {'Missing', 'Partial'})
    limit_review = sum(1 for row in rows if _label(row.get('limit_coverage')) != 'Complete')
    right_size = sum(
        1
        for row in rows
        if any(token in _text(row.get('recommendation'), '').lower() for token in ('reduce', 'increase', 'right-size'))
    )
    available = bool(rows)

    records = []
    for index, row in enumerate(rows[:5], start=1):
        records.append(
            {
                'ref': f'C{index}',
                'workload': _text(row.get('workload'), '-'),
                'namespace': _text(row.get('namespace'), '-'),
                'requests': _label(row.get('request_coverage'), 'Unknown'),
                'limits': _label(row.get('limit_coverage'), 'Unknown'),
                'qos': _label(row.get('qos'), 'Unknown'),
                'risk': _label(row.get('risk'), 'Unknown'),
                'tone': _tone(_label(row.get('risk'), 'Unknown')),
            }
        )

    return {
        'available': available,
        'total': total,
        'request_complete': request_complete,
        'limit_complete': limit_complete,
        'metrics_complete': metrics_complete,
        'best_effort': best_effort,
        'missing_requests': missing_requests,
        'limit_review': limit_review,
        'right_size': right_size,
        'request_coverage': _percent(request_complete, total),
        'limit_coverage': _percent(limit_complete, total),
        'metrics_coverage': _percent(metrics_complete, total),
        'metrics': (
            _metric(
                'CPU / Memory Requests',
                _percent_display(_percent(request_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and request_complete == total else 'warning',
            ),
            _metric(
                'Limits Coverage',
                _percent_display(_percent(limit_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and limit_complete == total else 'warning',
            ),
            _metric(
                'BestEffort',
                str(best_effort) if available else 'Not Available',
                'Review' if best_effort else 'Clear' if available else 'Not Available',
                'warning' if best_effort or not available else 'normal',
            ),
            _metric(
                'Metrics Coverage',
                _percent_display(_percent(metrics_complete, total)) if total else 'Not Available',
                'Complete Rows' if total else 'Not Available',
                'normal' if total and metrics_complete == total else 'warning',
            ),
        ),
        'coverage_rows': (
            {
                'label': 'Requests Complete',
                'value': _percent(request_complete, total) or 0.0,
                'display': _percent_display(_percent(request_complete, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Limits Complete',
                'value': _percent(limit_complete, total) or 0.0,
                'display': _percent_display(_percent(limit_complete, total)) if total else 'Not Available',
                'available': available,
            },
            {
                'label': 'Metrics Complete',
                'value': _percent(metrics_complete, total) or 0.0,
                'display': _percent_display(_percent(metrics_complete, total)) if total else 'Not Available',
                'available': available,
            },
        ),
        'records': records,
        'identities': tuple(
            {
                'ref': item['ref'],
                'title': item['workload'],
                'metadata': f'Namespace: {item["namespace"]}',
            }
            for item in records
        ),
        'decision': (
            'Prioritize incomplete requests, memory-limit review, BestEffort workloads, and incomplete metrics evidence before right-sizing.'
            if available
            else 'Restore workload request, limit, QoS, and metrics evidence before assigning configuration status.'
        ),
    }


def _governance_analysis(
    findings: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    quota_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = []
    for index, item in enumerate(findings[:6], start=1):
        severity = _text(item.get('severity'), 'warning').lower()
        title = _text(item.get('label'), 'Review workload governance finding')
        normalized.append(
            {
                'ref': f'G{index}',
                'title': title,
                'priority': _priority_from_severity(severity),
                'impact': 'High'
                if severity in {'critical', 'high'}
                else 'Medium'
                if severity in {'warning', 'medium'}
                else 'Low',
                'owner': 'Application Owner',
                'status': 'Open' if severity in {'critical', 'warning'} else 'Current',
                'tone': _tone(severity),
                'description': f'Review the related workload, namespace, or policy condition. Filter context: {_text(item.get("filter"), "-")}.',
            }
        )

    if not normalized:
        normalized.append(
            {
                'ref': 'G1',
                'title': 'No Critical Governance Findings Detected',
                'priority': 'P3',
                'impact': 'Low',
                'owner': 'Application Owner',
                'status': 'Current',
                'tone': 'normal',
                'description': 'Continue monitoring quota, requests, limits, QoS, and metrics coverage.',
            }
        )

    actionable_count = sum(1 for item in normalized if item['status'] in {'Open', 'Review'})
    critical_count = sum(1 for item in normalized if item['priority'] == 'P1')
    review_count = sum(1 for item in normalized if item['status'] in {'Open', 'Review'})
    signals = [
        {
            'ref': item['ref'],
            'signal': compact_governance_signal(item['title']),
            'namespace': 'Selected Scope',
            'state': item['status'],
            'tone': item['tone'],
        }
        for item in normalized
    ]
    return {
        'items': normalized,
        'signals': signals,
        'actionable_count': actionable_count,
        'critical_count': critical_count,
        'review_count': review_count,
        'metrics': (
            _metric(
                'Critical Findings',
                str(critical_count),
                'Open' if critical_count else 'Clear',
                'critical' if critical_count else 'normal',
            ),
            _metric(
                'Review Findings',
                str(review_count),
                'Requires Ownership' if review_count else 'Clear',
                'warning' if review_count else 'normal',
            ),
            _metric(
                'Quota Rows',
                str(len(quota_rows)) if quota_rows else 'Not Available',
                'Committed' if quota_rows else 'Not Available',
                'normal' if quota_rows else 'warning',
            ),
            _metric(
                'Workload Rows',
                str(len(mapping_rows)) if mapping_rows else 'Not Available',
                'Committed' if mapping_rows else 'Not Available',
                'normal' if mapping_rows else 'warning',
            ),
        ),
        'interpretation': (
            'Workload governance risk is derived from committed quota, configuration, QoS, metrics, and recommendation evidence. '
            'Confirm owner and live state before remediation.'
        ),
    }


def _recommendation_plan(
    recommendations: list[dict[str, Any]],
    governance: Mapping[str, Any],
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    items = []
    for item in recommendations:
        actionable = _is_actionable(item)
        if not actionable:
            continue
        priority = _priority(_text(item.get('priority'), 'Info'))
        items.append(
            {
                'priority': priority,
                'title': _text(item.get('title') or item.get('label'), 'Review Workload Governance Finding'),
                'description': _text(item.get('description'), 'Review the related workload analysis evidence.'),
                'owner': 'Application Owner',
                'target': _target(priority),
                'status': 'Open' if priority in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if priority == 'P1' else 'warning' if priority == 'P2' else 'info',
            }
        )

    if not items:
        for finding in governance.get('items', ()):
            if finding.get('status') not in {'Open', 'Review'}:
                continue
            items.append(
                {
                    'priority': finding['priority'],
                    'title': finding['title'],
                    'description': finding['description'],
                    'owner': finding['owner'],
                    'target': _target(finding['priority']),
                    'status': 'Open' if finding['priority'] in {'P1', 'P2'} else 'Planned',
                    'tone': finding['tone'],
                }
            )

    if not items:
        items.append(
            {
                'priority': 'P3',
                'title': 'Continue Workload Governance Monitoring',
                'description': 'No actionable finding was generated. Continue committed quota, requests, limits, QoS, and metrics monitoring.',
                'owner': 'Application Owner',
                'target': 'This Month',
                'status': 'Current',
                'tone': 'normal',
            }
        )

    rank = {'P1': 1, 'P2': 2, 'P3': 3}
    items.sort(key=lambda item: (rank.get(item['priority'], 9), item['title']))
    items = items[:5]
    for index, item in enumerate(items, start=1):
        item['ref'] = f'R{index}'

    p1 = sum(1 for item in items if item['priority'] == 'P1')
    p2 = sum(1 for item in items if item['priority'] == 'P2')
    p3 = sum(1 for item in items if item['priority'] == 'P3')
    return {
        'metrics': (
            _metric('P1 Actions', str(p1), 'Open' if p1 else 'None', 'critical' if p1 else 'normal'),
            _metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            _metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            _metric('Validation Gates', str(len(items)), 'Required', 'info'),
        ),
        'items': items,
        'governance': (
            {'field': 'Primary Action', 'requirement': items[0]['title']},
            {
                'field': 'Validation Criteria',
                'requirement': 'Confirm live state, owner, service objective, rollout window, and rollback readiness before closure.',
            },
            {'field': 'Assigned Owners', 'requirement': f'Application Owner: {len(items)} action(s).'},
            {
                'field': 'Change Control',
                'requirement': 'No request, limit, quota, replica, or autoscaling change is authorized by this report alone.',
            },
        ),
    }


def _executive_findings(
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    candidates = []
    if quota.get('missing'):
        candidates.append(
            (
                'P1',
                'Restore Missing ResourceQuota Coverage',
                f'{quota["missing"]} namespace(s) have missing quota coverage.',
                'Open',
                'critical',
            )
        )
    if configuration.get('missing_requests'):
        candidates.append(
            (
                'P1',
                'Validate Incomplete Resource Requests',
                f'{configuration["missing_requests"]} workload(s) have incomplete requests.',
                'Open',
                'critical',
            )
        )
    if configuration.get('limit_review'):
        candidates.append(
            (
                'P2',
                'Review Workload Limits',
                f'{configuration["limit_review"]} workload(s) require limit review.',
                'Review',
                'warning',
            )
        )
    if configuration.get('best_effort'):
        candidates.append(
            (
                'P1',
                'Review BestEffort Workloads',
                f'{configuration["best_effort"]} BestEffort workload(s) were detected.',
                'Open',
                'critical',
            )
        )
    if not candidates:
        candidates.append(
            (
                'P3',
                'Maintain Workload Governance Evidence',
                'No critical configuration gap was derived from the committed rows.',
                'Current',
                'normal',
            )
        )

    findings = []
    for index, (priority, title, description, status, tone) in enumerate(candidates[:4], start=1):
        findings.append(
            {
                'ref': f'F{index}',
                'priority': priority,
                'title': title,
                'description': description,
                'owner': 'Application Owner',
                'status': status,
                'tone': tone,
            }
        )
    return tuple(findings)


def _inventory_register(inventory: Mapping[str, Any], governance: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    return (
        {
            'ref': 'I1',
            'dimension': 'Workload Inventory',
            'scope': inventory['workload_display'],
            'evidence': 'Workload mapping rows',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I2',
            'dimension': 'Pod Participation',
            'scope': inventory['pod_display'],
            'evidence': 'Replica totals',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I3',
            'dimension': 'Namespace Scope',
            'scope': inventory['namespace_display'],
            'evidence': 'Quota and mapping rows',
            'status': inventory['status'],
            'tone': inventory['tone'],
        },
        {
            'ref': 'I4',
            'dimension': 'Governance Signals',
            'scope': str(governance['review_count']),
            'evidence': 'Committed findings',
            'status': 'Review' if governance['review_count'] else 'Current',
            'tone': 'warning' if governance['review_count'] else 'normal',
        },
    )


def _source_rows(
    payload: Mapping[str, Any],
    quota: Mapping[str, Any],
    mapping: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    supplied = payload.get('source_evidence')
    rows = []
    if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes)):
        for item in supplied:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    'source': _text(item.get('source'), 'Workload Evidence'),
                    'freshness': _text(item.get('freshness'), 'Committed'),
                    'last_collected': _date_text(item.get('last_collected')),
                }
            )
    if rows:
        return tuple(rows[:4])

    status = _mapping(payload.get('metrics_source_status'))
    response = status.get('response_time_ms') or status.get('response_time')
    freshness = f'{_float(response):.0f} ms' if response is not None and _float(response) > 0 else 'Committed'
    return (
        {'source': 'Metrics Source Workload Evidence', 'freshness': freshness, 'last_collected': 'At report cut-off'},
        {
            'source': 'Tenant Quota Analysis',
            'freshness': 'Committed' if quota['available'] else 'Not Available',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Workload Resource Mapping',
            'freshness': 'Committed' if mapping['available'] else 'Not Available',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Governance Recommendation Evidence',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        },
    )


def _executive_title(quota: Mapping[str, Any], configuration: Mapping[str, Any], governance: Mapping[str, Any]) -> str:
    if governance.get('critical_count'):
        return 'Critical workload governance findings require ownership.'
    if quota.get('missing') or configuration.get('missing_requests') or configuration.get('best_effort'):
        return 'Workload governance requires application-owner review.'
    return 'Committed workload posture is available for review.'


def _executive_body(
    inventory: Mapping[str, Any],
    quota: Mapping[str, Any],
    configuration: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> str:
    if not inventory.get('available'):
        return 'Committed workload rows are not available. No governance conclusion should be assigned.'
    return (
        f'The committed scope contains {inventory["workload_display"]} workload(s), '
        f'{inventory["pod_display"]} pod(s), and {inventory["namespace_display"]} namespace(s). '
        f'Quota coverage is {quota["coverage_display"]}; request coverage is '
        f'{_percent_display(configuration.get("request_coverage"))}. '
        f'{governance["actionable_count"]} finding(s) require ownership and validation.'
    )


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _reference(ref: str, title: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'description': description}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _text(value: Any, fallback: str = '-') -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _label(value: Any, fallback: str = '') -> str:
    if isinstance(value, Mapping):
        return _text(value.get('label'), fallback)
    return _text(value, fallback)


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _percent(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) * 100.0 / float(denominator), 1)


def _percent_display(value: Any) -> str:
    if value is None:
        return 'Not Available'
    return f'{_float(value):.1f}%'


def _tone(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'high', 'missing'}:
        return 'critical'
    if normalized in {'warning', 'watch', 'review', 'medium', 'partial', 'unknown'}:
        return 'warning'
    if normalized in {'info', 'planned'}:
        return 'info'
    return 'normal'


def _priority_from_severity(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'high'}:
        return 'P1'
    if normalized in {'warning', 'medium'}:
        return 'P2'
    return 'P3'


def _priority(value: str) -> str:
    normalized = value.lower()
    if normalized in {'critical', 'p1', 'high'}:
        return 'P1'
    if normalized in {'warning', 'p2', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def _target(priority: str) -> str:
    return 'This Week' if priority == 'P1' else 'Next Week' if priority == 'P2' else 'This Month'


def _is_actionable(item: Mapping[str, Any]) -> bool:
    value = item.get('is_actionable')
    if isinstance(value, bool):
        return value
    return _text(value, '').lower() in {'yes', 'true', '1'} or _priority(_text(item.get('priority'), 'Info')) in {'P1', 'P2'}


def _date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    return _text(value, 'At report cut-off')
