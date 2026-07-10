from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.intelligence.recommendation_engine import build_top_consumers_actionable_recommendations
from app.analytics.top_consumers.service import TopConsumersService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import get_selected_cluster as get_utilization_selected_cluster
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _as_pdf_list,
    _format_resource_number,
    _pdf_nested_label,
    _pdf_value,
    _safe_pdf_float,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)


def build_top_consumers_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_top_consumers_payload(
        report,
    )

    if payload.get('_error'):
        return build_top_consumers_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'top_namespace_consumers',
            'top_workload_consumers',
            'top_pod_consumers',
            'resource_hotspots',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Top Consumers Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Top Consumers service. '
                'It ranks CPU, memory, pod, and PVC consumers to identify operational hotspots. '
                'This report is for hotspot visibility and troubleshooting, not capacity forecasting.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    rendered_sections: set[str] = set()

    if 'executive_summary' in sections:
        story.extend(
            build_top_consumers_executive_summary(
                report,
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'executive_summary',
        )

    if 'top_namespace_consumers' in sections:
        story.extend(
            build_top_namespace_consumers_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'top_namespace_consumers',
        )

    if 'top_workload_consumers' in sections:
        story.extend(
            build_top_workload_consumers_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'top_workload_consumers',
        )

    if 'top_pod_consumers' in sections:
        story.extend(
            build_top_pod_consumers_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'top_pod_consumers',
        )

    if 'resource_hotspots' in sections:
        story.extend(
            build_top_consumers_hotspots_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'resource_hotspots',
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_top_consumers_recommendations_section(
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'operational_recommendations',
        )

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


def get_report_top_consumers_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Top Consumers report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        top_consumers_service = TopConsumersService(
            utilization_service,
        )

        prometheus_status = top_consumers_service.get_prometheus_status()

        selected_namespace = report.namespace or ''
        namespace_options = top_consumers_service.get_namespace_options()

        consumer_payload = top_consumers_service.get_top_consumers_payload(
            selected_namespace=selected_namespace,
            selected_resource='all',
            selected_search='',
            selected_sort='usage_percent',
            selected_focus='',
            page=1,
            per_page=1000,
        )

        actionable_recommendations = build_top_consumers_actionable_recommendations(
            consumer_payload,
        )
        consumer_payload = {
            **consumer_payload,
            'actionable_recommendations': actionable_recommendations,
        }

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
                'environment': str(
                    getattr(
                        cluster,
                        'environment',
                        '',
                    )
                    or ''
                ),
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
            'selected_time_range': report.period or '24h',
            'prometheus_status': prometheus_status,
            'namespace_options': namespace_options,
            'consumer_payload': consumer_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_top_consumers_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Top Consumers Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Top consumers payload unavailable',
            (
                'KAORI could not load the Top Consumers payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_top_consumers_executive_summary(
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

    consumer_payload = (
        payload.get(
            'consumer_payload',
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
            'Consumer Scope',
            'CPU, memory, pod count, and PVC usage ranking.',
        ],
        [
            'Has Data',
            consumer_payload.get(
                'has_data',
                False,
            ),
        ],
        [
            'Total Rows',
            consumer_payload.get(
                'total_rows',
                0,
            ),
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
                prometheus_status.get(
                    'error',
                    '-',
                ),
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
        *build_top_consumers_overview_summary(
            payload,
            styles,
        ),
    ]


def build_top_consumers_overview_summary(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    consumer_payload = (
        payload.get(
            'consumer_payload',
        )
        or {}
    )

    overview = (
        consumer_payload.get(
            'overview',
        )
        or {}
    )

    summary = (
        overview.get(
            'summary',
        )
        or {}
    )

    rows = [
        [
            'Metric',
            'Value',
            'Percent',
        ],
        [
            'Total CPU Used',
            _pdf_value(
                summary.get(
                    'total_cpu_used',
                    '-',
                )
            ),
            f'{_format_resource_number(summary.get("total_cpu_percent", 0))}%',
        ],
        [
            'Total Memory Used',
            _pdf_value(
                summary.get(
                    'total_memory_used',
                    '-',
                )
            ),
            f'{_format_resource_number(summary.get("total_memory_percent", 0))}%',
        ],
        [
            'Total Running Pods',
            _pdf_value(
                summary.get(
                    'total_pods',
                    0,
                )
            ),
            f'{_format_resource_number(summary.get("total_pods_percent", 0))}%',
        ],
        [
            'Total PVC Used',
            _pdf_value(
                summary.get(
                    'total_pvc_used',
                    '-',
                )
            ),
            f'{_format_resource_number(summary.get("total_pvc_percent", 0))}%',
        ],
    ]

    return [
        Paragraph(
            'Consumer Overview Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                5.4 * cm,
                5.4 * cm,
                5.4 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_top_consumers_summary_cards(
            payload,
            styles,
        ),
    ]


def build_top_consumers_summary_cards(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    consumer_payload = (
        payload.get(
            'consumer_payload',
        )
        or {}
    )

    summary_cards = (
        consumer_payload.get(
            'summary',
        )
        or {}
    )

    rows = [
        [
            'Card',
            'Consumer',
            'Value',
            'Risk',
            'Context',
        ],
    ]

    for key in [
        'highest_cpu',
        'highest_memory',
        'highest_pods',
        'highest_pvc',
    ]:
        card = summary_cards.get(
            key,
            {},
        )

        if not isinstance(
            card,
            dict,
        ):
            continue

        rows.append(
            [
                _pdf_value(
                    card.get(
                        'title',
                        key.replace(
                            '_',
                            ' ',
                        ).title(),
                    )
                ),
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
                _pdf_nested_label(
                    card,
                    'risk',
                ),
                _pdf_value(
                    card.get(
                        'subtitle',
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
                'No summary card data available.',
            ]
        )

    return [
        Paragraph(
            'Highest Consumer Cards',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.7 * cm,
                4.0 * cm,
                2.6 * cm,
                2.2 * cm,
                3.7 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_top_namespace_consumers_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = get_top_consumer_rows(
        payload,
    )

    namespace_rows = build_namespace_consumer_rows(
        rows,
    )

    table_rows: list[list[Any]] = [
        [
            'Namespace',
            'CPU Rows',
            'Memory Rows',
            'Pods Rows',
            'PVC Rows',
            'Hotspot Count',
        ],
    ]

    for item in namespace_rows[:10]:
        table_rows.append(
            [
                item['namespace'],
                item['cpu'],
                item['memory'],
                item['pods'],
                item['pvc'],
                item['hotspot_count'],
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                0,
                0,
                0,
                0,
                'No namespace consumer data available.',
            ]
        )

    return [
        Paragraph(
            'Top Namespace Consumers',
            styles['small_section_title'],
        ),
        Paragraph(
            'Namespace ranking is aggregated from visible CPU, memory, pod, and PVC consumer rows.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                4.2 * cm,
                2.2 * cm,
                2.4 * cm,
                2.2 * cm,
                2.2 * cm,
                3.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_namespace_consumer_rows(
    rows: list[Any],
) -> list[dict[str, Any]]:
    namespace_map: dict[str, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        namespace = str(
            row.get(
                'namespace',
                '-',
            )
            or '-'
        )

        resource_type = str(
            row.get(
                'resource_type',
                '',
            )
        )

        risk = _pdf_nested_label(
            row,
            'risk',
        )

        if namespace not in namespace_map:
            namespace_map[namespace] = {
                'namespace': namespace,
                'cpu': 0,
                'memory': 0,
                'pods': 0,
                'pvc': 0,
                'hotspot_count': 0,
            }

        if resource_type in [
            'cpu',
            'memory',
            'pods',
            'pvc',
        ]:
            namespace_map[namespace][resource_type] += 1

        if risk in [
            'Warning',
            'Critical',
        ]:
            namespace_map[namespace]['hotspot_count'] += 1

    return sorted(
        namespace_map.values(),
        key=lambda item: (
            int(
                item.get(
                    'hotspot_count',
                    0,
                )
            ),
            int(
                item.get(
                    'cpu',
                    0,
                )
            )
            + int(
                item.get(
                    'memory',
                    0,
                )
            )
            + int(
                item.get(
                    'pods',
                    0,
                )
            )
            + int(
                item.get(
                    'pvc',
                    0,
                )
            ),
            item.get(
                'namespace',
                '',
            ),
        ),
        reverse=True,
    )


def build_top_workload_consumers_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = get_top_consumer_rows(
        payload,
    )

    table_rows = [
        [
            'Rank',
            'Namespace',
            'Workload',
            'Resource',
            'Usage',
            'Usage %',
            'Risk',
        ],
    ]

    workload_rows = [
        row
        for row in rows
        if isinstance(
            row,
            dict,
        )
        and row.get(
            'resource_type',
        )
        in [
            'cpu',
            'memory',
            'pvc',
        ]
    ]

    for row in workload_rows[:15]:
        table_rows.append(
            [
                _pdf_value(
                    row.get(
                        'rank',
                        '-',
                    )
                ),
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
                        'resource_label',
                        row.get(
                            'resource_type',
                            '-',
                        ),
                    )
                ),
                _pdf_value(
                    row.get(
                        'current_display',
                        '-',
                    )
                ),
                f'{_format_resource_number(row.get("usage_percent", 0))}%',
                _pdf_nested_label(
                    row,
                    'risk',
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No workload consumer data available.',
            ]
        )

    return [
        Paragraph(
            'Top Workload Consumers',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                1.4 * cm,
                2.7 * cm,
                4.2 * cm,
                2.1 * cm,
                2.3 * cm,
                1.8 * cm,
                1.7 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        *build_top_consumers_detail_section(
            workload_rows,
            styles,
        ),
    ]


def build_top_pod_consumers_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = get_top_consumer_rows(
        payload,
    )

    pod_rows = [
        row
        for row in rows
        if isinstance(
            row,
            dict,
        )
        and (
            row.get(
                'pod',
            )
            or row.get(
                'resource_type',
            )
            == 'pods'
        )
    ]

    table_rows = [
        [
            'Rank',
            'Namespace',
            'Pod / Workload',
            'Container',
            'Resource',
            'Usage',
            'Risk',
        ],
    ]

    for row in pod_rows[:15]:
        pod_or_workload = row.get(
            'pod',
        ) or row.get(
            'workload',
            '-',
        )

        table_rows.append(
            [
                _pdf_value(
                    row.get(
                        'rank',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'namespace',
                        '-',
                    )
                ),
                _pdf_value(
                    pod_or_workload,
                ),
                _pdf_value(
                    row.get(
                        'container',
                        '-',
                    )
                    or '-'
                ),
                _pdf_value(
                    row.get(
                        'resource_label',
                        row.get(
                            'resource_type',
                            '-',
                        ),
                    )
                ),
                _pdf_value(
                    row.get(
                        'current_display',
                        '-',
                    )
                ),
                _pdf_nested_label(
                    row,
                    'risk',
                ),
            ]
        )

    if (
        len(
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No pod consumer data available.',
            ]
        )

    return [
        Paragraph(
            'Top Pod Consumers',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                1.4 * cm,
                2.7 * cm,
                4.0 * cm,
                2.8 * cm,
                2.0 * cm,
                2.0 * cm,
                1.3 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_top_consumers_hotspots_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = get_top_consumer_rows(
        payload,
    )

    hotspot_summary = build_consumer_hotspot_summary(
        rows,
    )

    table_rows = [
        [
            'Hotspot Area',
            'Count',
            'Description',
        ],
        [
            'Critical Consumers',
            hotspot_summary['critical_count'],
            'Rows with Critical risk label.',
        ],
        [
            'Warning Consumers',
            hotspot_summary['warning_count'],
            'Rows with Warning risk label.',
        ],
        [
            'Missing Requests',
            hotspot_summary['missing_request_count'],
            'CPU or memory rows with no configured request.',
        ],
        [
            'High Usage',
            hotspot_summary['high_usage_count'],
            'CPU or memory rows with usage percent >= 75%.',
        ],
        [
            'High PVC Usage',
            hotspot_summary['high_pvc_count'],
            'PVC rows with usage percent >= 80%.',
        ],
        [
            'Dominant Namespaces',
            ', '.join(
                hotspot_summary['dominant_namespaces'],
            )
            or '-',
            'Namespaces with repeated high-usage consumer rows.',
        ],
    ]

    return [
        Paragraph(
            'Resource Hotspots',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                5.0 * cm,
                3.2 * cm,
                8.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_consumer_hotspot_summary(
    rows: list[Any],
) -> dict[str, Any]:
    critical_count = 0
    warning_count = 0
    missing_request_count = 0
    high_usage_count = 0
    high_pvc_count = 0
    namespace_scores: dict[str, int] = {}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        resource_type = str(
            row.get(
                'resource_type',
                '',
            )
        )

        namespace = str(
            row.get(
                'namespace',
                '',
            )
        )

        risk = _pdf_nested_label(
            row,
            'risk',
        )

        usage_percent = _safe_pdf_float(
            row.get(
                'usage_percent',
                0,
            )
        )

        request = _safe_pdf_float(
            row.get(
                'request',
                0,
            )
        )

        if risk == 'Critical':
            critical_count += 1

        if risk == 'Warning':
            warning_count += 1

        if resource_type in [
            'cpu',
            'memory',
        ]:
            if request <= 0:
                missing_request_count += 1

            if usage_percent >= 75:
                high_usage_count += 1

        if resource_type == 'pvc' and usage_percent >= 80:
            high_pvc_count += 1

        if namespace and usage_percent >= 75:
            namespace_scores[namespace] = (
                namespace_scores.get(
                    namespace,
                    0,
                )
                + 1
            )

    dominant_namespaces = [
        namespace
        for namespace, _score in sorted(
            namespace_scores.items(),
            key=lambda item: (
                item[1],
                item[0],
            ),
            reverse=True,
        )[:3]
    ]

    return {
        'critical_count': critical_count,
        'warning_count': warning_count,
        'missing_request_count': missing_request_count,
        'high_usage_count': high_usage_count,
        'high_pvc_count': high_pvc_count,
        'dominant_namespaces': dominant_namespaces,
    }


def build_top_consumers_detail_section(
    rows: list[Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    table_rows = [
        [
            'Consumer',
            'Request',
            'Limit',
            'Recommendation',
        ],
    ]

    for row in rows[:10]:
        if not isinstance(
            row,
            dict,
        ):
            continue

        consumer_name = f'{_pdf_value(row.get("namespace", "-"))}/' f'{_pdf_value(row.get("workload", "-"))}'

        table_rows.append(
            [
                consumer_name,
                _pdf_value(
                    row.get(
                        'request_display',
                        '-',
                    )
                ),
                _pdf_value(
                    row.get(
                        'limit_display',
                        '-',
                    )
                ),
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
            table_rows,
        )
        == 1
    ):
        table_rows.append(
            [
                '-',
                '-',
                '-',
                'No consumer detail available.',
            ]
        )

    return [
        Paragraph(
            'Consumer Request / Limit Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            table_rows,
            styles,
            col_widths=[
                5.2 * cm,
                3.2 * cm,
                3.2 * cm,
                4.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_top_consumers_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    consumer_payload = (
        payload.get(
            'consumer_payload',
        )
        or {}
    )

    recommendations = consumer_payload.get(
        'actionable_recommendations',
        [],
    )

    if not isinstance(
        recommendations,
        list,
    ):
        recommendations = []

    if not recommendations:
        recommendations = build_top_consumers_actionable_recommendations(
            consumer_payload,
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
                'Review top consumers',
                'Info',
                'Top Consumers',
            ]
        )
        rows.append(
            [
                '',
                'No actionable consumer recommendation was generated. Continue monitoring CPU, memory, pod, and PVC hotspots.',  # noqa: E501
                'Context',
                '',
            ]
        )

    return [
        Paragraph(
            'Actionable Recommendations from Top Consumers',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from missing requests, high CPU/memory usage, '
                'dominant namespaces, and high PVC usage signals.'
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


def get_top_consumer_rows(
    payload: dict[str, Any],
) -> list[Any]:
    consumer_payload = (
        payload.get(
            'consumer_payload',
        )
        or {}
    )

    return _as_pdf_list(
        consumer_payload.get(
            'rows',
            [],
        )
    )
