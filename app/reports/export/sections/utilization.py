from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.analytics.utilization.service import (
    UtilizationService,
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_utilization_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _format_resource_number,
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)


def build_resource_utilization_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_resource_utilization_payload(
        report,
    )

    if payload.get('_error'):
        return build_resource_utilization_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'cpu_utilization',
            'memory_utilization',
            'storage_utilization',
            'pod_utilization',
            'node_resource_detail',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Resource Utilization Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Resource Utilization service. '
                'It uses the same Prometheus-backed data source used by the Utilization page.'
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
            build_resource_utilization_executive_summary(
                report,
                payload,
                styles,
            )
        )

    if 'resource_snapshot' in sections:
        story.extend(
            build_resource_utilization_summary_section(
                payload,
                styles,
            )
        )

    if 'cpu_utilization' in sections:
        story.extend(
            build_resource_utilization_metric_section(
                'CPU Utilization',
                'cpu',
                payload,
                styles,
            )
        )

    if 'memory_utilization' in sections:
        story.extend(
            build_resource_utilization_metric_section(
                'Memory Utilization',
                'memory',
                payload,
                styles,
            )
        )

    if 'storage_utilization' in sections:
        story.extend(
            build_resource_utilization_metric_section(
                'Storage Utilization',
                'storage',
                payload,
                styles,
            )
        )

    if 'pod_utilization' in sections:
        story.extend(
            build_resource_utilization_metric_section(
                'Pod Utilization',
                'pods',
                payload,
                styles,
            )
        )

    if 'node_resource_detail' in sections:
        story.extend(
            build_resource_utilization_cluster_detail_section(
                payload,
                styles,
            )
        )

    if 'risk_overview' in sections:
        story.extend(
            build_resource_utilization_risk_section(
                payload,
                styles,
            )
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_resource_utilization_recommendations_section(
                payload,
                styles,
            )
        )

    rendered_sections = {
        'executive_summary',
        'resource_snapshot',
        'cpu_utilization',
        'memory_utilization',
        'storage_utilization',
        'pod_utilization',
        'node_resource_detail',
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


def get_report_resource_utilization_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Resource Utilization report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        service = UtilizationService(
            prometheus,
        )

        prometheus_status = service.get_prometheus_status()
        summary = service.get_summary()
        summary_table = service.get_summary_table(
            summary,
        )
        cluster_info = service.get_cluster_info(
            summary,
        )
        risk_assessment = service.get_capacity_pressure_risk(
            summary,
        )
        top_cpu_consumers = service.get_top_cpu_consumers()
        top_memory_consumers = service.get_top_memory_consumers()

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
            'summary': summary,
            'summary_table': summary_table,
            'cluster_info': cluster_info,
            'risk_assessment': risk_assessment,
            'top_cpu_consumers': top_cpu_consumers[:5],
            'top_memory_consumers': top_memory_consumers[:5],
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_resource_utilization_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Resource Utilization Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Utilization payload unavailable',
            (
                'KAORI could not load the Resource Utilization payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_resource_utilization_executive_summary(
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
            report.period or '24h',
        ],
        [
            'Kubernetes Version',
            cluster_info.get(
                'kubernetes_version',
                '-',
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
        [
            'Prometheus Response Time',
            f'{_pdf_value(prometheus_status.get("response_time_ms", "-"))} ms',
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


def build_resource_utilization_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    summary_table = payload.get(
        'summary_table',
        [],
    )

    rows = [
        [
            'Resource',
            'Capacity',
            'Usage',
            'Utilization',
            'Scope',
        ],
    ]

    if not isinstance(
        summary_table,
        list,
    ):
        summary_table = []

    for item in summary_table:
        if not isinstance(
            item,
            dict,
        ):
            continue

        rows.append(
            [
                _pdf_value(
                    item.get(
                        'resource',
                        '-',
                    )
                ),
                _format_resource_number(
                    item.get(
                        'capacity',
                        0,
                    )
                ),
                _format_resource_number(
                    item.get(
                        'usage',
                        0,
                    )
                ),
                f'{_format_resource_number(item.get("utilization", 0))}%',
                _pdf_value(
                    item.get(
                        'scope',
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
                'No utilization summary data available.',
            ]
        )

    return [
        Paragraph(
            'Resource Utilization Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.0 * cm,
                3.0 * cm,
                3.0 * cm,
                2.7 * cm,
                4.5 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_resource_utilization_metric_section(
    title: str,
    resource_key: str,
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    metric = get_utilization_summary_metric(
        payload,
        resource_key,
    )

    risk = get_utilization_risk_metric(
        payload,
        resource_key,
    )

    rows = [
        [
            'Metric',
            'Value',
        ],
        [
            'Capacity',
            metric.get(
                'capacity',
                '-',
            ),
        ],
        [
            'Usage',
            metric.get(
                'usage',
                '-',
            ),
        ],
        [
            'Utilization',
            metric.get(
                'utilization',
                '-',
            ),
        ],
        [
            'Scope',
            metric.get(
                'scope',
                '-',
            ),
        ],
        [
            'Status',
            risk.get(
                'status',
                '-',
            ),
        ],
        [
            'Pressure Nodes',
            risk.get(
                'pressure_nodes',
                0,
            ),
        ],
        [
            'Reason',
            risk.get(
                'reason',
                '-',
            ),
        ],
    ]

    return [
        Paragraph(
            title,
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                5.2 * cm,
                11.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def get_utilization_summary_metric(
    payload: dict[str, Any],
    resource_key: str,
) -> dict[str, str]:
    summary_table = payload.get(
        'summary_table',
        [],
    )

    if not isinstance(
        summary_table,
        list,
    ):
        summary_table = []

    normalized_key = normalize_resource_key(
        resource_key,
    )

    for item in summary_table:
        if not isinstance(
            item,
            dict,
        ):
            continue

        item_key = normalize_resource_key(
            item.get(
                'resource',
                '',
            )
        )

        if item_key != normalized_key:
            continue

        return {
            'capacity': format_utilization_metric_value(
                item.get(
                    'capacity',
                    '-',
                )
            ),
            'usage': format_utilization_metric_value(
                item.get(
                    'usage',
                    '-',
                )
            ),
            'utilization': format_utilization_percent(
                item.get(
                    'utilization',
                    '-',
                )
            ),
            'scope': _pdf_value(
                item.get(
                    'scope',
                    '-',
                )
            ),
        }

    summary = (
        payload.get(
            'summary',
        )
        or {}
    )

    fallback_map = {
        'cpu': {
            'capacity': summary.get(
                'cpu_capacity',
                '-',
            ),
            'usage': summary.get(
                'cpu_usage',
                summary.get(
                    'cpu_used',
                    '-',
                ),
            ),
            'utilization': summary.get(
                'cpu_utilization',
                summary.get(
                    'cpu_percent',
                    '-',
                ),
            ),
            'scope': 'Cluster',
        },
        'memory': {
            'capacity': summary.get(
                'memory_capacity',
                '-',
            ),
            'usage': summary.get(
                'memory_usage',
                summary.get(
                    'memory_used',
                    '-',
                ),
            ),
            'utilization': summary.get(
                'memory_utilization',
                summary.get(
                    'memory_percent',
                    '-',
                ),
            ),
            'scope': 'Cluster',
        },
        'storage': {
            'capacity': summary.get(
                'storage_capacity_gib',
                summary.get(
                    'storage_capacity',
                    '-',
                ),
            ),
            'usage': summary.get(
                'storage_usage_gib',
                summary.get(
                    'storage_used',
                    '-',
                ),
            ),
            'utilization': summary.get(
                'storage_utilization',
                summary.get(
                    'storage_percent',
                    '-',
                ),
            ),
            'scope': 'Cluster',
        },
        'pods': {
            'capacity': summary.get(
                'pod_capacity',
                '-',
            ),
            'usage': summary.get(
                'running_pods',
                summary.get(
                    'pod_usage',
                    summary.get(
                        'pods_used',
                        '-',
                    ),
                ),
            ),
            'utilization': summary.get(
                'pod_utilization',
                summary.get(
                    'pod_percent',
                    '-',
                ),
            ),
            'scope': 'Cluster',
        },
    }

    fallback = fallback_map.get(
        normalized_key,
        {},
    )

    return {
        'capacity': format_utilization_metric_value(
            fallback.get(
                'capacity',
                '-',
            )
        ),
        'usage': format_utilization_metric_value(
            fallback.get(
                'usage',
                '-',
            )
        ),
        'utilization': format_utilization_percent(
            fallback.get(
                'utilization',
                '-',
            )
        ),
        'scope': _pdf_value(
            fallback.get(
                'scope',
                '-',
            )
        ),
    }


def get_utilization_risk_metric(
    payload: dict[str, Any],
    resource_key: str,
) -> dict[str, Any]:
    risk_assessment = (
        payload.get(
            'risk_assessment',
        )
        or {}
    )

    normalized_key = normalize_resource_key(
        resource_key,
    )

    item = (
        risk_assessment.get(
            normalized_key,
        )
        or {}
    )

    if not isinstance(
        item,
        dict,
    ):
        return {
            'status': '-',
            'pressure_nodes': 0,
            'reason': '-',
        }

    return {
        'status': _pdf_value(
            item.get(
                'status',
                '-',
            )
        ),
        'pressure_nodes': _pdf_value(
            item.get(
                'pressure_nodes',
                0,
            )
        ),
        'reason': _pdf_value(
            item.get(
                'reason',
                '-',
            )
        ),
    }


def normalize_resource_key(
    value: Any,
) -> str:
    normalized = (
        str(
            value,
        )
        .strip()
        .lower()
        .replace(
            ' ',
            '_',
        )
        .replace(
            '-',
            '_',
        )
    )

    aliases = {
        'cpu_utilization': 'cpu',
        'cpu_usage': 'cpu',
        'memory_utilization': 'memory',
        'memory_usage': 'memory',
        'mem': 'memory',
        'storage_utilization': 'storage',
        'storage_usage': 'storage',
        'pod': 'pods',
        'pod_utilization': 'pods',
        'pod_usage': 'pods',
    }

    return aliases.get(
        normalized,
        normalized,
    )


def format_utilization_metric_value(
    value: Any,
) -> str:
    if value in (
        None,
        '',
        '-',
    ):
        return '-'

    if isinstance(
        value,
        str,
    ):
        return value

    return _format_resource_number(
        value,
    )


def format_utilization_percent(
    value: Any,
) -> str:
    if value in (
        None,
        '',
        '-',
    ):
        return '-'

    if isinstance(
        value,
        str,
    ):
        cleaned_value = value.strip()

        if cleaned_value.endswith(
            '%',
        ):
            return cleaned_value

        return f'{cleaned_value}%'

    return f'{_format_resource_number(value)}%'


def build_resource_utilization_cluster_detail_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    cluster_info = (
        payload.get(
            'cluster_info',
        )
        or {}
    )

    summary = (
        payload.get(
            'summary',
        )
        or {}
    )

    rows = [
        [
            'Kubernetes Version',
            cluster_info.get(
                'kubernetes_version',
                '-',
            ),
        ],
        [
            'Total Nodes',
            cluster_info.get(
                'total_nodes',
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
            'CPU Capacity',
            summary.get(
                'cpu_capacity',
                0,
            ),
        ],
        [
            'Memory Capacity',
            summary.get(
                'memory_capacity',
                0,
            ),
        ],
        [
            'Storage Capacity',
            f'{_format_resource_number(summary.get("storage_capacity_gib", 0))} GiB',
        ],
        [
            'Pod Capacity',
            summary.get(
                'pod_capacity',
                0,
            ),
        ],
    ]

    return [
        Paragraph(
            'Cluster Resource Detail',
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


def build_resource_utilization_risk_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    risk_assessment = (
        payload.get(
            'risk_assessment',
        )
        or {}
    )

    rows = [
        [
            'Resource',
            'Status',
            'Utilization',
            'Pressure Nodes',
            'Reason',
        ],
    ]

    for resource in [
        'cpu',
        'memory',
        'storage',
        'pods',
    ]:
        item = risk_assessment.get(
            resource,
            {},
        )

        rows.append(
            [
                resource.upper(),
                _pdf_value(
                    item.get(
                        'status',
                        '-',
                    )
                ),
                f'{_format_resource_number(item.get("utilization", 0))}%',
                _pdf_value(
                    item.get(
                        'pressure_nodes',
                        0,
                    )
                ),
                _pdf_value(
                    item.get(
                        'reason',
                        '-',
                    )
                ),
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
                2.6 * cm,
                2.8 * cm,
                2.8 * cm,
                3.0 * cm,
                5.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]

    story.extend(
        build_resource_utilization_top_consumers_section(
            payload,
            styles,
        )
    )

    return story


def build_resource_utilization_top_consumers_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    top_cpu_consumers = payload.get(
        'top_cpu_consumers',
        [],
    )

    top_memory_consumers = payload.get(
        'top_memory_consumers',
        [],
    )

    rows = [
        [
            'Type',
            'Namespace',
            'Pod',
            'Value',
        ],
    ]

    _append_utilization_consumers(
        rows,
        'CPU',
        top_cpu_consumers,
    )

    _append_utilization_consumers(
        rows,
        'Memory',
        top_memory_consumers,
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
                'No top consumer data available.',
            ]
        )

    return [
        Paragraph(
            'Top Resource Consumers',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                2.4 * cm,
                4.2 * cm,
                6.2 * cm,
                3.4 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def _append_utilization_consumers(
    rows: list[list[Any]],
    consumer_type: str,
    consumers: Any,
) -> None:
    if not isinstance(
        consumers,
        list,
    ):
        return

    for consumer in consumers[:5]:
        if not isinstance(
            consumer,
            dict,
        ):
            continue

        value = consumer.get(
            'value',
            0,
        )

        rows.append(
            [
                consumer_type,
                _pdf_value(
                    consumer.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    consumer.get(
                        'pod',
                        '-',
                    )
                ),
                _format_resource_number(
                    value,
                ),
            ]
        )


def build_resource_utilization_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = build_utilization_actionable_recommendations(
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

    return [
        Paragraph(
            'Actionable Recommendations from Resource Utilization',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from utilization risk assessment and top consumer signals. '
                'Critical and warning items represent actionable findings.'
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


def build_resource_utilization_recommendations(
    risk_assessment: dict[str, Any],
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []

    for resource in [
        'cpu',
        'memory',
        'storage',
        'pods',
    ]:
        item = risk_assessment.get(
            resource,
            {},
        )

        status = str(
            item.get(
                'status',
                'Normal',
            )
        )

        utilization = _format_resource_number(
            item.get(
                'utilization',
                0,
            )
        )

        if status == 'Critical':
            recommendations.append(
                {
                    'label': (
                        f'Review {resource.upper()} immediately. '
                        f'Current utilization is {utilization}% or pressure condition is active.'
                    ),
                    'priority': 'Critical',
                }
            )
            continue

        if status == 'Warning':
            recommendations.append(
                {
                    'label': (
                        f'Review {resource.upper()} utilization trend. '
                        f'Current utilization is {utilization}% and may require capacity or request adjustment.'
                    ),
                    'priority': 'Warning',
                }
            )

    if not recommendations:
        recommendations.extend(
            [
                {
                    'label': 'No critical utilization pressure detected. Continue regular resource monitoring.',
                    'priority': 'Normal',
                },
                {
                    'label': 'Review top CPU and memory consumers periodically to detect recurring hotspots.',
                    'priority': 'Info',
                },
                {
                    'label': 'Validate workload requests and limits if utilization patterns are consistently high or too low.',
                    'priority': 'Info',
                },
            ]
        )

    return recommendations
