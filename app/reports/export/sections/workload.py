from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.analytics.workload.service import WorkloadAnalysisService
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_workload_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _as_pdf_list,
    _format_resource_number,
    _pdf_nested_label,
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)


def build_workload_analysis_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_workload_analysis_payload(
        report,
    )

    if payload.get('_error'):
        return build_workload_analysis_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'tenant_quota_summary',
            'request_limit_coverage',
            'workload_resource_mapping',
            'governance_findings',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Workload Analysis Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Workload Analysis service. '
                'It focuses on tenant quota coverage, workload request and limit governance, QoS posture, '
                'runtime efficiency, and right-sizing recommendations.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    if 'executive_summary' in sections:
        story.extend(
            build_workload_executive_summary(
                report,
                payload,
                styles,
            )
        )

    if 'tenant_quota_summary' in sections:
        story.extend(
            build_workload_tenant_quota_section(
                payload,
                styles,
            )
        )

    if 'request_limit_coverage' in sections:
        story.extend(
            build_workload_request_limit_section(
                payload,
                styles,
            )
        )

    if 'workload_resource_mapping' in sections:
        story.extend(
            build_workload_resource_mapping_section(
                payload,
                styles,
            )
        )

    if 'governance_findings' in sections:
        story.extend(
            build_workload_governance_findings_section(
                payload,
                styles,
            )
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_workload_recommendations_section(
                payload,
                styles,
            )
        )

    rendered_sections = {
        'executive_summary',
        'tenant_quota_summary',
        'request_limit_coverage',
        'workload_resource_mapping',
        'governance_findings',
        'operational_recommendations',
    }

    for section in sections:
        if section in rendered_sections:
            continue

        story.extend(
            build_single_section_content(
                section,
                styles,
            )
        )

    return story


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
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_workload_analysis_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Workload Analysis Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Workload payload unavailable',
            (
                'KAORI could not load the Workload Analysis payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_workload_executive_summary(
    report: Report,
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    cluster = (
        payload.get(
            'cluster',
        )
        or {}
    )

    prometheus_status = (
        payload.get(
            'prometheus_status',
        )
        or {}
    )

    namespace_options = payload.get(
        'namespace_options',
        [],
    )

    tenant_quota_rows = _as_pdf_list(
        payload.get(
            'tenant_quota_rows',
            [],
        )
    )

    workload_mapping_rows = _as_pdf_list(
        payload.get(
            'workload_mapping_rows',
            [],
        )
    )

    rows = [
        [
            'Selected Cluster',
            cluster.get(
                'name',
                'Unknown Cluster',
            ),
        ],
        [
            'Cluster ID',
            cluster.get(
                'id',
                report.cluster_id or '-',
            ),
        ],
        [
            'Namespace Scope',
            payload.get(
                'selected_namespace',
                'All Namespaces',
            ),
        ],
        [
            'Time Range',
            payload.get(
                'selected_time_range',
                report.period or '24h',
            ),
        ],
        [
            'Workload Scope',
            'ResourceQuota, workload requests, workload limits, QoS, runtime usage, and right-sizing signals.',
        ],
        [
            'Namespace Options',
            len(
                namespace_options,
            )
            if isinstance(
                namespace_options,
                list,
            )
            else 0,
        ],
        [
            'Tenant Rows',
            len(
                tenant_quota_rows,
            ),
        ],
        [
            'Workload Rows',
            len(
                workload_mapping_rows,
            ),
        ],
        [
            'Prometheus Status',
            prometheus_status.get(
                'label',
                'Unknown',
            ),
        ],
        [
            'Prometheus Message',
            prometheus_status.get(
                'description',
                '-',
            ),
        ],
    ]

    return [
        Paragraph(
            'Executive Summary',
            styles['small_section_title'],
        ),
        build_key_value_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_workload_tenant_quota_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    tenant_quota_summary = (
        payload.get(
            'tenant_quota_summary',
        )
        or {}
    )

    summary_cards = tenant_quota_summary.get(
        'summary_cards',
        [],
    )

    tenant_rows = _as_pdf_list(
        payload.get(
            'tenant_quota_rows',
            [],
        )
    )

    story: list[Any] = [
        Paragraph(
            'Tenant Quota Summary',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Tenant quota summary compares ResourceQuota hard/used values with runtime CPU, memory, '
                'and pod usage per namespace.'
            ),
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
    ]

    card_rows = [
        [
            'Metric',
            'Value',
            'Caption',
        ],
    ]

    if isinstance(
        summary_cards,
        list,
    ):
        for card in summary_cards:
            if not isinstance(
                card,
                dict,
            ):
                continue

            card_rows.append(
                [
                    _pdf_value(
                        card.get(
                            'label',
                            '-',
                        )
                    ),
                    _pdf_value(
                        card.get(
                            'value',
                            '-',
                        )
                    ),
                    _pdf_value(
                        card.get(
                            'caption',
                            '-',
                        )
                    ),
                ]
            )

    if (
        len(
            card_rows,
        )
        == 1
    ):
        card_rows.append(
            [
                '-',
                '-',
                'No tenant quota summary available.',
            ]
        )

    story.append(
        build_pdf_table(
            card_rows,
            styles,
            col_widths=[
                4.2 * cm,
                3.4 * cm,
                8.6 * cm,
            ],
        )
    )

    story.append(
        Spacer(
            1,
            0.25 * cm,
        )
    )

    tenant_detail_rows = [
        [
            'Namespace',
            'Quota Status',
            'Quota Usage',
            'Actual Usage',
            'Risk',
            'Recommendation',
        ],
    ]

    for row in tenant_rows[:10]:
        if not isinstance(
            row,
            dict,
        ):
            continue

        quota_status = _pdf_nested_label(
            row,
            'quota_status',
        )

        risk = _pdf_nested_label(
            row,
            'risk',
        )

        tenant_detail_rows.append(
            [
                _pdf_value(
                    row.get(
                        'namespace',
                        '-',
                    )
                ),
                quota_status,
                f'{_format_resource_number(row.get("quota_usage_percent", 0))}%',
                f'{_format_resource_number(row.get("actual_usage_percent", 0))}%',
                risk,
                _pdf_value(
                    row.get(
                        'recommendation',
                        '-',
                    )
                ),
            ]
        )

    if (
        len(
            tenant_detail_rows,
        )
        == 1
    ):
        tenant_detail_rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                'No tenant quota row data available.',
            ]
        )

    story.extend(
        [
            Paragraph(
                'Tenant Quota Detail',
                styles['small_section_title'],
            ),
            build_pdf_table(
                tenant_detail_rows,
                styles,
                col_widths=[
                    2.8 * cm,
                    2.6 * cm,
                    2.3 * cm,
                    2.3 * cm,
                    2.0 * cm,
                    4.2 * cm,
                ],
            ),
            Spacer(
                1,
                0.3 * cm,
            ),
        ]
    )

    return story


def build_workload_request_limit_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    workload_rows = _as_pdf_list(
        payload.get(
            'workload_mapping_rows',
            [],
        )
    )

    summary = get_workload_request_limit_summary(
        workload_rows,
    )

    rows = [
        [
            'Signal',
            'Count',
            'Description',
        ],
        [
            'Total Workloads',
            summary['total_workloads'],
            'Total workload rows in selected namespace scope.',
        ],
        [
            'Complete',
            summary['complete_count'],
            'Workloads with CPU/memory requests and limits.',
        ],
        [
            'Missing Requests',
            summary['missing_request_count'],
            'Workloads missing CPU or memory requests, including BestEffort workloads.',
        ],
        [
            'Missing Limits',
            summary['missing_limit_count'],
            'Workloads missing CPU or memory limits, including BestEffort workloads.',
        ],
        [
            'BestEffort',
            summary['best_effort_count'],
            'Workloads classified as BestEffort or missing both requests and limits.',
        ],
        [
            'Over-requested',
            summary['over_requested_count'],
            'Workloads with reduce recommendation based on runtime usage versus requests.',
        ],
        [
            'Under-requested',
            summary['under_requested_count'],
            'Workloads with increase recommendation based on runtime usage versus requests.',
        ],
        [
            'High Risk',
            summary['high_risk_count'],
            'Workloads with High risk label.',
        ],
        [
            'Medium Risk',
            summary['medium_risk_count'],
            'Workloads with Medium risk label.',
        ],
    ]

    return [
        Paragraph(
            'Request & Limit Coverage',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                4.4 * cm,
                2.4 * cm,
                9.4 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def get_workload_request_limit_summary(
    workload_rows: list[Any],
) -> dict[str, int]:
    total_workloads = 0
    complete_count = 0
    missing_request_count = 0
    missing_limit_count = 0
    best_effort_count = 0
    over_requested_count = 0
    under_requested_count = 0
    high_risk_count = 0
    medium_risk_count = 0

    for row in workload_rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        total_workloads += 1

        resource_status = _pdf_nested_label(
            row,
            'resource_status',
        )

        qos = _pdf_nested_label(
            row,
            'qos',
        )

        risk = _pdf_nested_label(
            row,
            'risk',
        )

        recommendation = str(
            row.get(
                'recommendation',
                '',
            )
        ).lower()

        if resource_status == 'Complete':
            complete_count += 1

        if resource_status in [
            'Missing Request',
            'BestEffort',
        ]:
            missing_request_count += 1

        if resource_status in [
            'Missing Limit',
            'BestEffort',
        ]:
            missing_limit_count += 1

        if resource_status == 'BestEffort' or qos == 'BestEffort':
            best_effort_count += 1

        if 'reduce' in recommendation:
            over_requested_count += 1

        if 'increase' in recommendation:
            under_requested_count += 1

        if risk == 'High':
            high_risk_count += 1

        if risk == 'Medium':
            medium_risk_count += 1

    return {
        'total_workloads': total_workloads,
        'complete_count': complete_count,
        'missing_request_count': missing_request_count,
        'missing_limit_count': missing_limit_count,
        'best_effort_count': best_effort_count,
        'over_requested_count': over_requested_count,
        'under_requested_count': under_requested_count,
        'high_risk_count': high_risk_count,
        'medium_risk_count': medium_risk_count,
    }


def build_workload_resource_mapping_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    workload_rows = _as_pdf_list(
        payload.get(
            'workload_mapping_rows',
            [],
        )
    )

    rows = [
        [
            'Namespace',
            'Workload',
            'Type',
            'Replicas',
            'Status',
            'QoS',
            'Risk',
        ],
    ]

    for row in workload_rows[:10]:
        if not isinstance(
            row,
            dict,
        ):
            continue

        rows.append(
            [
                _pdf_value(
                    row.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'workload',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'type',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'replicas',
                        0,
                    )
                ),
                _pdf_nested_label(
                    row,
                    'resource_status',
                ),
                _pdf_nested_label(
                    row,
                    'qos',
                ),
                _pdf_nested_label(
                    row,
                    'risk',
                ),
            ]
        )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No workload mapping data available.',
            ]
        )

    story: list[Any] = [
        Paragraph(
            'Workload Resource Mapping',
            styles['small_section_title'],
        ),
        Paragraph(
            'Top workload rows are sorted by governance risk from the Workload Analysis service.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                2.5 * cm,
                3.6 * cm,
                2.2 * cm,
                1.7 * cm,
                2.5 * cm,
                1.8 * cm,
                1.9 * cm,
            ],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    story.extend(
        build_workload_resource_usage_detail_section(
            workload_rows,
            styles,
        )
    )

    return story


def build_workload_resource_usage_detail_section(
    workload_rows: list[Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        [
            'Workload',
            'CPU Summary',
            'Memory Summary',
            'Efficiency',
            'Recommendation',
        ],
    ]

    for row in workload_rows[:8]:
        if not isinstance(
            row,
            dict,
        ):
            continue

        rows.append(
            [
                f'{_pdf_value(row.get("namespace", "-"))}/{_pdf_value(row.get("workload", "-"))}',
                _pdf_value(
                    row.get(
                        'cpu_summary',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'memory_summary',
                        '-',
                    )
                ),
                f'{_format_resource_number(row.get("efficiency", 0))}%',
                _pdf_value(
                    row.get(
                        'recommendation',
                        '-',
                    )
                ),
            ]
        )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                'No workload usage detail available.',
            ]
        )

    return [
        Paragraph(
            'Workload Usage Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.8 * cm,
                3.8 * cm,
                3.8 * cm,
                1.8 * cm,
                3.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_workload_governance_findings_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    governance_findings = payload.get(
        'governance_findings',
        [],
    )

    rows = [
        [
            'Finding',
            'Severity',
            'Filter',
        ],
    ]

    if isinstance(
        governance_findings,
        list,
    ):
        for item in governance_findings:
            if not isinstance(
                item,
                dict,
            ):
                continue

            rows.append(
                [
                    _pdf_value(
                        item.get(
                            'label',
                            '-',
                        )
                    ),
                    _pdf_value(
                        item.get(
                            'severity',
                            '-',
                        )
                    ),
                    _pdf_value(
                        item.get(
                            'filter',
                            '-',
                        )
                    ),
                ]
            )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                'No critical governance findings detected.',
                'Healthy',
                '-',
            ]
        )

    return [
        Paragraph(
            'Governance Findings',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                9.6 * cm,
                3.0 * cm,
                3.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_workload_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = payload.get(
        'actionable_recommendations',
        [],
    )

    if not isinstance(
        recommendations,
        list,
    ):
        recommendations = build_workload_actionable_recommendations(
            payload,
        )

    rows = [
        [
            'No',
            'Recommendation',
            'Priority',
            'Source',
        ],
    ]

    for index, item in enumerate(
        recommendations,
        start=1,
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        rows.append(
            [
                str(
                    index,
                ),
                _pdf_value(
                    item.get(
                        'title',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'priority',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'source_label',
                        item.get(
                            'source',
                            '-',
                        ),
                    )
                ),
            ]
        )

        rows.append(
            [
                '',
                _pdf_value(
                    item.get(
                        'description',
                        '-',
                    )
                ),
                'Actionable'
                if item.get(
                    'is_actionable',
                    'No',
                )
                == 'Yes'
                else 'Context',
                '',
            ]
        )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '1',
                'Review workload governance posture',
                'Normal',
                'Workload baseline',
            ]
        )

        rows.append(
            [
                '',
                (
                    'No actionable workload recommendation was generated. Continue monitoring '
                    'ResourceQuota coverage, requests, limits, QoS, and right-sizing signals.'
                ),
                'Context',
                '',
            ]
        )

    return [
        Paragraph(
            'Actionable Recommendations from Workload Analysis',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from tenant quota rows, workload resource mapping, '
                'and governance findings. Critical and warning items represent actionable findings.'
            ),
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                1.2 * cm,
                8.0 * cm,
                3.0 * cm,
                4.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]
