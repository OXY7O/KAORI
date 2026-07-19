from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.cluster.constants import get_environment_label
from app.analytics.capacity.service import CapacityService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import get_selected_cluster as get_utilization_selected_cluster
from app.intelligence.recommendation_engine import build_capacity_actionable_recommendations
from app.models.report import Report
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _format_resource_number,
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)

CAPACITY_REAL_DATA_SECTIONS = {
    'executive_summary',
    'worker_capacity_summary',
    'resource_allocation_headroom',
    'capacity_pressure_risk',
    'operational_recommendations',
}


def get_capacity_real_data_sections(
    report: Report,
) -> list[str]:
    sections = report.sections_as_list()

    if not sections:
        return [
            'executive_summary',
            'worker_capacity_summary',
            'resource_allocation_headroom',
            'capacity_pressure_risk',
            'operational_recommendations',
        ]

    filtered_sections = [section for section in sections if section in CAPACITY_REAL_DATA_SECTIONS]

    if filtered_sections:
        return filtered_sections

    return [
        'executive_summary',
        'worker_capacity_summary',
        'resource_allocation_headroom',
        'capacity_pressure_risk',
        'operational_recommendations',
    ]


def build_capacity_analysis_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_capacity_analysis_payload(
        report,
    )

    if payload.get('_error'):
        return build_capacity_analysis_error_section(
            payload,
            styles,
        )

    sections = get_capacity_real_data_sections(
        report,
    )

    story: list[Any] = [
        Paragraph(
            'Capacity Analysis Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Capacity Analysis service. '
                'Capacity values use worker-node schedulable capacity scope, excluding control-plane nodes.'
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
            build_capacity_executive_summary(
                report,
                payload,
                styles,
            )
        )

    if 'worker_capacity_summary' in sections:
        story.extend(
            build_capacity_worker_summary_section(
                payload,
                styles,
            )
        )

    if 'resource_allocation_headroom' in sections:
        story.extend(
            build_capacity_allocation_headroom_section(
                payload,
                styles,
            )
        )

    if 'capacity_pressure_risk' in sections:
        story.extend(
            build_capacity_risk_section(
                payload,
                styles,
            )
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_capacity_recommendations_section(
                payload,
                styles,
            )
        )

    rendered_sections = {
        'executive_summary',
        'worker_capacity_summary',
        'resource_allocation_headroom',
        'capacity_pressure_risk',
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


def get_report_capacity_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Capacity Analysis report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        capacity_service = CapacityService(
            utilization_service,
            PrometheusConsumer(cluster),
        )

        prometheus_status = utilization_service.get_prometheus_status()

        capacity_payload = capacity_service.get_capacity_analysis(
            time_range=report.period or '24h',
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
            'prometheus_status': prometheus_status,
            **capacity_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_capacity_analysis_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Capacity Analysis Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Capacity payload unavailable',
            (
                'KAORI could not load the Capacity Analysis payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_capacity_executive_summary(
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

    cluster_info = (
        payload.get(
            'cluster_info',
        )
        or {}
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
            'Time Range',
            payload.get(
                'selected_time_range',
                report.period or '24h',
            ),
        ],
        [
            'Capacity Scope',
            'Worker / schedulable capacity. Control-plane nodes are excluded from allocatable capacity.',
        ],
        [
            'Total Nodes',
            cluster_info.get(
                'total_nodes',
                0,
            ),
        ],
        [
            'Worker Nodes',
            cluster_info.get(
                'worker_nodes',
                0,
            ),
        ],
        [
            'Control Plane Nodes',
            cluster_info.get(
                'master_nodes',
                0,
            ),
        ],
        [
            'Ready Nodes',
            cluster_info.get(
                'ready_nodes',
                0,
            ),
        ],
        [
            'Not Ready Nodes',
            cluster_info.get(
                'not_ready_nodes',
                0,
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


def build_capacity_worker_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    worker_capacity_summary = (
        payload.get(
            'worker_capacity_summary',
        )
        or {}
    )

    cards = worker_capacity_summary.get(
        'cards',
        [],
    )

    rows = [
        [
            'Metric',
            'Value',
            'Caption',
            'Context',
        ],
    ]

    if isinstance(
        cards,
        list,
    ):
        for card in cards:
            if not isinstance(
                card,
                dict,
            ):
                continue

            rows.append(
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
                    _pdf_value(
                        card.get(
                            'footer',
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
                'No worker capacity summary available.',
            ]
        )

    return [
        Paragraph(
            'Worker Capacity Summary',
            styles['small_section_title'],
        ),
        Paragraph(
            _pdf_value(
                worker_capacity_summary.get(
                    'subtitle',
                    'Schedulable capacity is calculated from worker nodes.',
                )
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
                3.8 * cm,
                3.2 * cm,
                4.4 * cm,
                4.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_capacity_allocation_headroom_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    capacity_summary = (
        payload.get(
            'capacity_summary',
        )
        or {}
    )

    allocation_summary = (
        payload.get(
            'allocation_summary',
        )
        or {}
    )

    story: list[Any] = [
        Paragraph(
            'Resource Allocation & Headroom',
            styles['small_section_title'],
        ),
        Paragraph(
            'This table compares worker allocatable capacity, current usage, available headroom, requests, limits, actual average usage, and peak usage where available.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
    ]

    headroom_rows = [
        [
            'Resource',
            'Capacity',
            'Used',
            'Available',
            'Headroom',
        ],
    ]

    for resource in [
        'cpu',
        'memory',
        'pods',
    ]:
        item = capacity_summary.get(
            resource,
            {},
        )

        unit = 'cores'

        if resource == 'memory':
            unit = 'GiB'

        if resource == 'pods':
            unit = 'pods'

        headroom_rows.append(
            [
                'Pods' if resource == 'pods' else resource.upper(),
                f'{_format_resource_number(item.get("capacity", 0))} {unit}',
                f'{_format_resource_number(item.get("used", 0))} {unit}',
                f'{_format_resource_number(item.get("available", 0))} {unit}',
                f'{_format_resource_number(item.get("headroom", 0))}%',
            ]
        )

    story.append(
        build_pdf_table(
            headroom_rows,
            styles,
            col_widths=[
                3.0 * cm,
                3.3 * cm,
                3.3 * cm,
                3.3 * cm,
                3.3 * cm,
            ],
        )
    )

    story.append(
        Spacer(
            1,
            0.25 * cm,
        )
    )

    for resource in [
        'cpu',
        'memory',
        'pods',
    ]:
        section = allocation_summary.get(
            resource,
            {},
        )

        story.extend(
            build_capacity_allocation_resource_table(
                resource,
                section,
                styles,
            )
        )

    return story


def build_capacity_allocation_resource_table(
    resource: str,
    section: Any,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    if not isinstance(
        section,
        dict,
    ):
        return []

    title = _pdf_value(
        section.get(
            'title',
            resource.upper(),
        )
    )

    unit = _pdf_value(
        section.get(
            'unit',
            '',
        )
    )

    status = section.get(
        'status',
        {},
    )

    status_label = '-'

    if isinstance(
        status,
        dict,
    ):
        status_label = _pdf_value(
            status.get(
                'label',
                '-',
            )
        )

    rows = [
        [
            'Signal',
            'Display',
            'Percent',
        ],
    ]

    items = section.get(
        'items',
        [],
    )

    if isinstance(
        items,
        list,
    ):
        for item in items:
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
                            'display',
                            '-',
                        )
                    ),
                    f'{_format_resource_number(item.get("percent", 0))}%',
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
                'No allocation data available.',
            ]
        )

    return [
        Paragraph(
            f'{title} Allocation Status: {status_label} ({unit})',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                5.0 * cm,
                7.4 * cm,
                3.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]


def build_capacity_risk_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    risk_summary = payload.get(
        'risk_summary',
        [],
    )

    governance_findings = payload.get(
        'governance_findings',
        [],
    )

    rows = [
        [
            'Resource',
            'Headroom',
            'Status',
        ],
    ]

    if isinstance(
        risk_summary,
        list,
    ):
        for item in risk_summary:
            if not isinstance(
                item,
                dict,
            ):
                continue

            status = item.get(
                'status',
                {},
            )

            status_label = '-'

            if isinstance(
                status,
                dict,
            ):
                status_label = status.get(
                    'label',
                    '-',
                )

            rows.append(
                [
                    _pdf_value(
                        item.get(
                            'label',
                            '-',
                        )
                    ),
                    f'{_format_resource_number(item.get("headroom", 0))}%',
                    _pdf_value(
                        status_label,
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
                'No capacity risk data available.',
            ]
        )

    story: list[Any] = [
        Paragraph(
            'Capacity & Pressure Risk',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                5.0 * cm,
                4.0 * cm,
                7.2 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]

    story.extend(
        build_capacity_governance_findings_section(
            governance_findings,
            styles,
        )
    )

    return story


def build_capacity_governance_findings_section(
    governance_findings: Any,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
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
                'No capacity governance finding detected.',
                'Healthy',
                '-',
            ]
        )

    return [
        Paragraph(
            'Capacity Governance Findings',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                9.4 * cm,
                3.0 * cm,
                3.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_capacity_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = build_capacity_actionable_recommendations(
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
                        'source',
                        '-',
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
                'Continue monitoring capacity posture',
                'Normal',
                'Capacity baseline',
            ]
        )

    return [
        Paragraph(
            'Actionable Recommendations from Capacity Analysis',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from real capacity risk summary, headroom thresholds, '
                'and governance findings. Static report-type guidance is used only as baseline context elsewhere.'
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
