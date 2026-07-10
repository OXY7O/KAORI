from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.analytics.overview.service import get_analytics_overview
from app.models.report import Report
from app.reports.export.helpers import (
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)


def build_analytics_overview_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_analytics_overview_payload(
        report,
    )

    if payload.get('_error'):
        return build_analytics_overview_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    story: list[Any] = [
        Paragraph(
            'Analytics Overview Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Analytics Overview payload. '
                'It reuses the same service data used by the Analytics Overview page.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    if not sections:
        sections = [
            'executive_summary',
            'analytics_summary',
            'resource_snapshot',
            'risk_overview',
            'operational_recommendations',
        ]

    if 'executive_summary' in sections:
        story.extend(
            build_analytics_executive_summary(
                report,
                payload,
                styles,
            )
        )

    if 'analytics_summary' in sections:
        story.extend(
            build_analytics_summary_section(
                payload,
                styles,
            )
        )

    if 'resource_snapshot' in sections:
        story.extend(
            build_analytics_resource_snapshot_section(
                payload,
                styles,
            )
        )

    if 'risk_overview' in sections:
        story.extend(
            build_analytics_risk_overview_section(
                payload,
                styles,
            )
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_analytics_recommendations_section(
                payload,
                styles,
            )
        )

    rendered_sections = {
        'executive_summary',
        'analytics_summary',
        'resource_snapshot',
        'risk_overview',
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


def get_report_analytics_overview_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        selected_cluster_id = report.cluster_id or None
        time_range = report.period or '24h'

        return get_analytics_overview(
            selected_cluster_id=selected_cluster_id,
            time_range=time_range,
        )
    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_analytics_overview_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Analytics Overview Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Analytics payload unavailable',
            (
                'KAORI could not load the Analytics Overview payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_analytics_executive_summary(
    report: Report,
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    selected_cluster = (
        payload.get(
            'selected_cluster',
        )
        or {}
    )

    prometheus = (
        payload.get(
            'prometheus',
        )
        or {}
    )

    selected_cluster_name = selected_cluster.get(
        'name',
        'Unknown Cluster',
    )

    selected_cluster_id = (
        payload.get(
            'selected_cluster_id',
            report.cluster_id or '-',
        )
        or '-'
    )

    if report.cluster_id:
        scope_rows = [
            [
                'Selected Cluster',
                selected_cluster_name,
            ],
            [
                'Cluster ID',
                selected_cluster_id,
            ],
        ]
    else:
        scope_rows = [
            [
                'Selected Scope',
                'All Clusters',
            ],
            [
                'Reference Cluster',
                selected_cluster_name,
            ],
            [
                'Reference Cluster ID',
                selected_cluster_id,
            ],
        ]

    rows = [
        *scope_rows,
        [
            'Time Range',
            payload.get(
                'selected_time_range',
                report.period or '-',
            ),
        ],
        [
            'Last Analyzed',
            payload.get(
                'last_analyzed_at',
                '-',
            ),
        ],
        [
            'Prometheus Status',
            prometheus.get(
                'status_label',
                'Unknown',
            ),
        ],
        [
            'Prometheus Message',
            prometheus.get(
                'message',
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


def build_analytics_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    clusters = payload.get(
        'clusters',
        [],
    )

    health_summary = (
        payload.get(
            'health_summary',
        )
        or {}
    )

    cluster_health = health_summary.get(
        'cluster_health',
        {},
    )

    resource_pressure = health_summary.get(
        'resource_pressure',
        {},
    )

    capacity_risk = health_summary.get(
        'capacity_risk',
        {},
    )

    active_alerts = health_summary.get(
        'active_alerts',
        {},
    )

    forecast_risk = health_summary.get(
        'forecast_risk',
        {},
    )

    rows = [
        [
            'Metric',
            'Value',
            'Status',
            'Description',
        ],
        [
            'Available Clusters',
            str(
                len(
                    clusters,
                )
            ),
            'Inventory',
            'Total clusters available in the Analytics Overview filter.',
        ],
        [
            'Cluster Health',
            _pdf_value(
                cluster_health.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                cluster_health.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                cluster_health.get(
                    'description',
                    '-',
                )
            ),
        ],
        [
            'Resource Pressure',
            _pdf_value(
                resource_pressure.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                resource_pressure.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                resource_pressure.get(
                    'description',
                    '-',
                )
            ),
        ],
        [
            'Capacity Risk',
            _pdf_value(
                capacity_risk.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                capacity_risk.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                capacity_risk.get(
                    'description',
                    '-',
                )
            ),
        ],
        [
            'Active Alerts',
            _pdf_value(
                active_alerts.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                active_alerts.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                active_alerts.get(
                    'description',
                    '-',
                )
            ),
        ],
        [
            'Forecast Risk',
            _pdf_value(
                forecast_risk.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                forecast_risk.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                forecast_risk.get(
                    'description',
                    '-',
                )
            ),
        ],
    ]

    return [
        Paragraph(
            'Analytics Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.4 * cm,
                3.0 * cm,
                3.0 * cm,
                6.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_analytics_resource_snapshot_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    resource_snapshot = (
        payload.get(
            'resource_snapshot',
        )
        or {}
    )

    rows = [
        [
            'Resource',
            'Value',
            'Percent',
            'Status',
            'Description',
        ],
    ]

    for key in [
        'cpu',
        'memory',
        'storage',
        'pods',
    ]:
        item = resource_snapshot.get(
            key,
            {},
        )

        rows.append(
            [
                _pdf_value(
                    item.get(
                        'label',
                        key.title(),
                    )
                ),
                _pdf_value(
                    item.get(
                        'value',
                        '-',
                    )
                ),
                f'{_pdf_value(item.get("percent", 0))}%',
                _pdf_value(
                    item.get(
                        'status',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'description',
                        '-',
                    )
                ),
            ]
        )

    return [
        Paragraph(
            'Resource Snapshot',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.4 * cm,
                2.4 * cm,
                2.2 * cm,
                2.6 * cm,
                5.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_analytics_capacity_storage_workload_snapshot(
            payload,
            styles,
        ),
    ]


def build_analytics_capacity_storage_workload_snapshot(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    capacity_snapshot = (
        payload.get(
            'capacity_snapshot',
        )
        or {}
    )

    storage_snapshot = (
        payload.get(
            'storage_snapshot',
        )
        or {}
    )

    workload_snapshot = (
        payload.get(
            'workload_snapshot',
        )
        or {}
    )

    capacity_rows = [
        [
            'Signal',
            'Value',
            'Unit',
            'Status',
        ],
    ]

    for key in [
        'cpu_headroom',
        'memory_headroom',
        'pod_capacity_remaining',
        'recommendations',
    ]:
        item = capacity_snapshot.get(
            key,
            {},
        )

        capacity_rows.append(
            [
                key.replace(
                    '_',
                    ' ',
                ).title(),
                _pdf_value(
                    item.get(
                        'value',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'unit',
                        '',
                    )
                ),
                _pdf_value(
                    item.get(
                        'status',
                        '-',
                    )
                ),
            ]
        )

    storage_rows = [
        [
            'Storage Signal',
            'Value',
        ],
        [
            'PVC Requested',
            _pdf_value(
                storage_snapshot.get(
                    'pvc_requested',
                    '-',
                )
            ),
        ],
        [
            'PVC Used',
            _pdf_value(
                storage_snapshot.get(
                    'pvc_used',
                    '-',
                )
            ),
        ],
        [
            'PVC Free',
            _pdf_value(
                storage_snapshot.get(
                    'pvc_free',
                    '-',
                )
            ),
        ],
        [
            'Used Percent',
            f'{_pdf_value(storage_snapshot.get("used_percent", 0))}%',
        ],
        [
            'PVC Risk Count',
            _pdf_value(
                storage_snapshot.get(
                    'pvc_risk_count',
                    0,
                )
            ),
        ],
        [
            'Top Namespace',
            _pdf_value(
                storage_snapshot.get(
                    'top_namespace',
                    '-',
                )
            ),
        ],
    ]

    workload_rows = [
        [
            'Workload Signal',
            'Value',
        ],
        [
            'Missing CPU Requests',
            _pdf_value(
                workload_snapshot.get(
                    'missing_cpu_requests',
                    0,
                )
            ),
        ],
        [
            'Missing Memory Requests',
            _pdf_value(
                workload_snapshot.get(
                    'missing_memory_requests',
                    0,
                )
            ),
        ],
        [
            'Missing CPU Limits',
            _pdf_value(
                workload_snapshot.get(
                    'missing_cpu_limits',
                    0,
                )
            ),
        ],
        [
            'Missing Memory Limits',
            _pdf_value(
                workload_snapshot.get(
                    'missing_memory_limits',
                    0,
                )
            ),
        ],
        [
            'Over Provisioned',
            _pdf_value(
                workload_snapshot.get(
                    'over_provisioned',
                    0,
                )
            ),
        ],
        [
            'Under Provisioned',
            _pdf_value(
                workload_snapshot.get(
                    'under_provisioned',
                    0,
                )
            ),
        ],
    ]

    return [
        Paragraph(
            'Capacity Snapshot',
            styles['small_section_title'],
        ),
        build_pdf_table(
            capacity_rows,
            styles,
            col_widths=[
                5.2 * cm,
                3.4 * cm,
                3.0 * cm,
                4.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
        Paragraph(
            'Storage Snapshot',
            styles['small_section_title'],
        ),
        build_key_value_table(
            storage_rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
        Paragraph(
            'Workload Snapshot',
            styles['small_section_title'],
        ),
        build_key_value_table(
            workload_rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_analytics_risk_overview_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    alerts_snapshot = (
        payload.get(
            'alerts_snapshot',
        )
        or {}
    )

    forecast_snapshot = (
        payload.get(
            'forecast_snapshot',
        )
        or {}
    )

    top_risk_namespace = (
        payload.get(
            'health_summary',
        )
        or {}
    ).get(
        'top_risk_namespace',
        {},
    )

    rows = [
        [
            'Risk Area',
            'Value',
            'Status',
            'Description',
        ],
        [
            'Firing Alerts',
            _pdf_value(
                alerts_snapshot.get(
                    'firing_alerts',
                    0,
                )
            ),
            _pdf_value(
                alerts_snapshot.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                alerts_snapshot.get(
                    'highest_severity_description',
                    '-',
                )
            ),
        ],
        [
            'Critical Alerts',
            _pdf_value(
                alerts_snapshot.get(
                    'critical_alerts',
                    0,
                )
            ),
            _pdf_value(
                alerts_snapshot.get(
                    'highest_severity',
                    '-',
                )
            ),
            'Critical alert count in the selected cluster scope.',
        ],
        [
            'Recent Anomalies',
            _pdf_value(
                alerts_snapshot.get(
                    'recent_anomalies',
                    0,
                )
            ),
            'Candidate',
            'Recent anomaly candidates detected by the alerts/anomalies module.',
        ],
        [
            'Forecast Risk',
            _pdf_value(
                forecast_snapshot.get(
                    'forecast_risk',
                    '-',
                )
            ),
            _pdf_value(
                forecast_snapshot.get(
                    'forecast_horizon',
                    '-',
                )
            ),
            _pdf_value(
                forecast_snapshot.get(
                    'risk_note',
                    '-',
                )
            ),
        ],
        [
            'Highest Projected Resource',
            _pdf_value(
                forecast_snapshot.get(
                    'highest_projected_resource',
                    '-',
                )
            ),
            f'{_pdf_value(forecast_snapshot.get("highest_projected_percent", 0))}%',
            'Highest projected resource utilization from forecast payload.',
        ],
        [
            'Top Risk Namespace',
            _pdf_value(
                top_risk_namespace.get(
                    'value',
                    '-',
                )
            ),
            _pdf_value(
                top_risk_namespace.get(
                    'status',
                    '-',
                )
            ),
            _pdf_value(
                top_risk_namespace.get(
                    'description',
                    '-',
                )
            ),
        ],
    ]

    story: list[Any] = [
        Paragraph(
            'Risk Overview',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                4.2 * cm,
                3.0 * cm,
                3.0 * cm,
                6.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]

    story.extend(
        build_analytics_top_consumers_summary(
            payload,
            styles,
        )
    )

    return story


def build_analytics_top_consumers_summary(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    top_consumers = (
        payload.get(
            'top_consumers',
        )
        or {}
    )

    rows = [
        [
            'Category',
            'Name',
            'Namespace',
            'Value',
            'Percent',
        ],
    ]

    for category in [
        'cpu',
        'memory',
        'storage',
    ]:
        items = top_consumers.get(
            category,
            [],
        )

        if not items:
            rows.append(
                [
                    category.upper(),
                    '-',
                    '-',
                    'No data',
                    '-',
                ]
            )
            continue

        first_item = items[0]

        rows.append(
            [
                category.upper(),
                _pdf_value(
                    first_item.get(
                        'name',
                        '-',
                    )
                ),
                _pdf_value(
                    first_item.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    first_item.get(
                        'display_value',
                        first_item.get(
                            'value',
                            '-',
                        ),
                    )
                ),
                f'{_pdf_value(first_item.get("percent", 0))}%',
            ]
        )

    return [
        Paragraph(
            'Top Consumer Signals',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.0 * cm,
                4.2 * cm,
                3.4 * cm,
                3.0 * cm,
                2.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_analytics_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = normalize_analytics_recommendations(
        payload.get(
            'recommendations',
            [],
        )
    )

    rows = [
        [
            'No',
            'Recommendation',
            'Priority',
        ],
    ]

    if not recommendations:
        rows.append(
            [
                '1',
                'No operational recommendation was generated by the Analytics Overview payload.',
                'Info',
            ]
        )
    else:
        for index, item in enumerate(
            recommendations,
            start=1,
        ):
            rows.append(
                [
                    str(
                        index,
                    ),
                    item['label'],
                    item['priority'],
                ]
            )

    return [
        Paragraph(
            'Operational Recommendations from Analytics Overview',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                1.4 * cm,
                11.8 * cm,
                3.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def normalize_analytics_recommendations(
    recommendations: Any,
) -> list[dict[str, str]]:
    if not isinstance(
        recommendations,
        list,
    ):
        return []

    normalized: list[dict[str, str]] = []

    for item in recommendations[:8]:
        if isinstance(
            item,
            dict,
        ):
            label = (
                item.get(
                    'label',
                )
                or item.get(
                    'title',
                )
                or item.get(
                    'description',
                )
                or item.get(
                    'message',
                )
                or 'Review analytics recommendation.'
            )

            priority = (
                item.get(
                    'priority',
                )
                or item.get(
                    'severity',
                )
                or item.get(
                    'tone',
                )
                or 'Info'
            )

            normalized.append(
                {
                    'label': str(
                        label,
                    ),
                    'priority': str(
                        priority,
                    ).title(),
                }
            )
            continue

        normalized.append(
            {
                'label': str(
                    item,
                ),
                'priority': 'Info',
            }
        )

    return normalized
