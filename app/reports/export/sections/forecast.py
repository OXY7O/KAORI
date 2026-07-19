from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.cluster.constants import get_environment_label
from app.analytics.forecast.service import ForecastAnalysisService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import get_selected_cluster as get_utilization_selected_cluster
from app.intelligence.recommendation_engine import build_forecast_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _as_pdf_list,
    _format_resource_number,
    _pdf_value,
    _safe_pdf_float,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
    format_forecast_eta,
)


def build_resource_forecast_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_resource_forecast_payload(
        report,
    )

    if payload.get('_error'):
        return build_resource_forecast_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'memory_forecast',
            'storage_forecast',
            'pod_forecast',
            'capacity_projection',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Resource Forecast Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Forecast Analysis service. '
                'Forecast values are planning signals based on historical Prometheus usage and projected growth. '
                'They are not active alerts.'
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
            build_forecast_executive_summary(
                report,
                payload,
                styles,
            )
        )
        rendered_sections.add(
            'executive_summary',
        )

    if 'forecast_summary' in sections or 'forecast_risk_summary' in sections or 'resource_trend_summary' in sections:
        story.extend(
            build_forecast_risk_summary_section(
                payload,
                styles,
            )
        )
        story.extend(
            build_forecast_trend_summary_section(
                payload,
                styles,
            )
        )
        rendered_sections.update(
            {
                'forecast_summary',
                'forecast_risk_summary',
                'resource_trend_summary',
            }
        )

    resource_section_map = {
        'cpu_forecast': 'cpu',
        'memory_forecast': 'memory',
        'storage_forecast': 'storage',
        'pod_forecast': 'pods',
    }

    for section, resource_key in resource_section_map.items():
        if section not in sections:
            continue

        story.extend(
            build_forecast_single_resource_section(
                payload,
                styles,
                resource_key=resource_key,
            )
        )
        rendered_sections.add(
            section,
        )

    if 'capacity_projection' in sections or 'forecast_projection' in sections or 'threshold_eta' in sections:
        story.extend(
            build_forecast_projection_section(
                payload,
                styles,
            )
        )
        story.extend(
            build_forecast_threshold_section(
                payload,
                styles,
            )
        )
        rendered_sections.update(
            {
                'capacity_projection',
                'forecast_projection',
                'threshold_eta',
            }
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_forecast_recommendations_section(
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


def get_report_resource_forecast_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Resource Forecast report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        prometheus_status = utilization_service.get_prometheus_status()

        forecast_service = ForecastAnalysisService(
            utilization_service=utilization_service,
            cluster=cluster,
        )

        selected_namespace = report.namespace or ''
        history_window = normalize_report_forecast_history_window(
            report.period or '30d',
        )
        forecast_horizon = normalize_report_forecast_horizon(
            report.period or '90d',
        )

        namespace_options = forecast_service.get_namespace_options()

        forecast_payload = forecast_service.get_forecast_analysis(
            namespace=selected_namespace,
            history_window=history_window,
            forecast_horizon=forecast_horizon,
            resource='all',
        )

        actionable_recommendations = build_forecast_actionable_recommendations(
            forecast_payload,
        )

        forecast_payload = {
            **forecast_payload,
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
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'prometheus_status': prometheus_status,
            'namespace_options': namespace_options,
            'forecast_payload': forecast_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_resource_forecast_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Resource Forecast Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Forecast payload unavailable',
            (
                'KAORI could not load the Resource Forecast payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def normalize_report_forecast_history_window(
    value: str,
) -> str:
    if value in [
        '7d',
        '30d',
        '90d',
    ]:
        return value

    if value in [
        '1h',
        '6h',
        '24h',
    ]:
        return '7d'

    return '30d'


def normalize_report_forecast_horizon(
    value: str,
) -> str:
    if value in [
        '7d',
        '30d',
        '90d',
        '180d',
        '365d',
    ]:
        return value

    return '90d'


def build_forecast_executive_summary(
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

    forecast_payload = (
        payload.get(
            'forecast_payload',
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
            'History Window',
            forecast_payload.get(
                'history_window',
                payload.get(
                    'history_window',
                    '30d',
                ),
            ),
        ],
        [
            'Forecast Horizon',
            forecast_payload.get(
                'forecast_horizon',
                payload.get(
                    'forecast_horizon',
                    '90d',
                ),
            ),
        ],
        [
            'Forecast Scope',
            'CPU, memory, storage, and pods projection based on historical Prometheus usage.',
        ],
        [
            'Generated At',
            forecast_payload.get(
                'generated_at',
                '-',
            )
            or '-',
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
    ]


def build_forecast_risk_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    summary = (
        forecast_payload.get(
            'summary',
        )
        or {}
    )

    nearest_warning = summary.get(
        'nearest_warning',
        {},
    )

    nearest_critical = summary.get(
        'nearest_critical',
        {},
    )

    rows = [
        [
            'Metric',
            'Value',
            'Description',
        ],
        [
            'Has Data',
            _pdf_value(
                forecast_payload.get(
                    'has_data',
                    False,
                )
            ),
            _pdf_value(
                forecast_payload.get(
                    'message',
                    'Forecast payload contains usable data.',
                )
                or 'Forecast payload contains usable data.'
            ),
        ],
        [
            'Total Resources',
            _pdf_value(
                summary.get(
                    'total_resources',
                    0,
                )
            ),
            'Total resources included in this forecast.',
        ],
        [
            'Warning Count',
            _pdf_value(
                summary.get(
                    'warning_count',
                    0,
                )
            ),
            'Resources projected to reach warning threshold.',
        ],
        [
            'Critical Count',
            _pdf_value(
                summary.get(
                    'critical_count',
                    0,
                )
            ),
            'Resources projected to reach critical threshold.',
        ],
        [
            'Highest Projected Resource',
            _pdf_value(
                summary.get(
                    'highest_projected_label',
                    'N/A',
                )
            ),
            f'{_format_resource_number(summary.get("highest_projected_percent", 0))}% projected utilization.',
        ],
        [
            'Nearest Warning',
            format_forecast_eta(
                nearest_warning,
            ),
            'Nearest projected warning threshold breach.',
        ],
        [
            'Nearest Critical',
            format_forecast_eta(
                nearest_critical,
            ),
            'Nearest projected critical threshold breach.',
        ],
    ]

    return [
        Paragraph(
            'Forecast Risk Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                4.6 * cm,
                4.4 * cm,
                7.2 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_forecast_trend_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    items = _as_pdf_list(
        forecast_payload.get(
            'items',
            [],
        )
    )

    rows = [
        [
            'Resource',
            'Status',
            'Current',
            'Projected',
            'Growth',
            'Confidence',
        ],
    ]

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
                        'status_label',
                        item.get(
                            'status',
                            '-',
                        ),
                    )
                ),
                f'{_pdf_value(item.get("current_display", "-"))} ({_format_resource_number(item.get("current_percent", 0))}%)',  # noqa: E501
                f'{_pdf_value(item.get("projected_display", "-"))} ({_format_resource_number(item.get("projected_percent", 0))}%)',  # noqa: E501
                _pdf_value(
                    item.get(
                        'growth_display',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'confidence',
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
                '-',
                'No forecast resource trend data available.',
            ]
        )

    return [
        Paragraph(
            'Resource Trend Summary',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                2.7 * cm,
                2.2 * cm,
                3.5 * cm,
                3.5 * cm,
                2.5 * cm,
                1.8 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_forecast_single_resource_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    *,
    resource_key: str,
) -> list[Any]:
    item = get_forecast_item_by_key(
        payload,
        resource_key,
    )

    if not item:
        return [
            Paragraph(
                f'{resource_key.replace("_", " ").title()} Forecast',
                styles['small_section_title'],
            ),
            build_status_banner(
                'Forecast data unavailable',
                f'No forecast item was returned for resource key: {resource_key}.',
            ),
            Spacer(
                1,
                0.3 * cm,
            ),
        ]

    historical_points = _as_pdf_list(
        item.get(
            'historical_points',
            [],
        )
    )

    forecast_points = _as_pdf_list(
        item.get(
            'forecast_points',
            [],
        )
    )

    rows = [
        [
            'Metric',
            'Value',
        ],
        [
            'Resource',
            _pdf_value(
                item.get(
                    'label',
                    resource_key.title(),
                )
            ),
        ],
        [
            'Description',
            _pdf_value(
                item.get(
                    'description',
                    '-',
                )
            ),
        ],
        [
            'Status',
            _pdf_value(
                item.get(
                    'status_label',
                    item.get(
                        'status',
                        '-',
                    ),
                )
            ),
        ],
        [
            'Capacity',
            _pdf_value(
                item.get(
                    'capacity_display',
                    '-',
                )
            ),
        ],
        [
            'Current Usage',
            f'{_pdf_value(item.get("current_display", "-"))} ({_format_resource_number(item.get("current_percent", 0))}%)',  # noqa: E501
        ],
        [
            'Projected Usage',
            f'{_pdf_value(item.get("projected_display", "-"))} ({_format_resource_number(item.get("projected_percent", 0))}%)',  # noqa: E501
        ],
        [
            'Growth',
            _pdf_value(
                item.get(
                    'growth_display',
                    '-',
                )
            ),
        ],
        [
            'Warning ETA',
            format_forecast_eta(
                item.get(
                    'warning_eta',
                    {},
                )
            ),
        ],
        [
            'Critical ETA',
            format_forecast_eta(
                item.get(
                    'critical_eta',
                    {},
                )
            ),
        ],
        [
            'Confidence',
            _pdf_value(
                item.get(
                    'confidence',
                    '-',
                )
            ),
        ],
        [
            'Confidence Reason',
            _pdf_value(
                item.get(
                    'confidence_reason',
                    '-',
                )
            ),
        ],
        [
            'Data Points',
            f'{len(historical_points)} historical / {len(forecast_points)} forecast',
        ],
    ]

    return [
        Paragraph(
            f'{_pdf_value(item.get("label", resource_key.title()))} Forecast',
            styles['small_section_title'],
        ),
        build_key_value_table(
            rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def get_forecast_item_by_key(
    payload: dict[str, Any],
    resource_key: str,
) -> dict[str, Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    items = _as_pdf_list(
        forecast_payload.get(
            'items',
            [],
        )
    )

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        if (
            item.get(
                'key',
            )
            == resource_key
        ):
            return item

    return {}


def build_forecast_projection_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    items = _as_pdf_list(
        forecast_payload.get(
            'items',
            [],
        )
    )

    rows = [
        [
            'Resource',
            'Capacity',
            'Current %',
            'Projected %',
            'Delta',
            'Data Points',
        ],
    ]

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        current_percent = _safe_pdf_float(
            item.get(
                'current_percent',
                0,
            )
        )

        projected_percent = _safe_pdf_float(
            item.get(
                'projected_percent',
                0,
            )
        )

        historical_points = _as_pdf_list(
            item.get(
                'historical_points',
                [],
            )
        )

        forecast_points = _as_pdf_list(
            item.get(
                'forecast_points',
                [],
            )
        )

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
                        'capacity_display',
                        '-',
                    )
                ),
                f'{_format_resource_number(current_percent)}%',
                f'{_format_resource_number(projected_percent)}%',
                f'{_format_resource_number(projected_percent - current_percent)}%',
                f'{len(historical_points)} historical / {len(forecast_points)} forecast',
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
                'No projection data available.',
            ]
        )

    return [
        Paragraph(
            'Forecast Projection Table',
            styles['small_section_title'],
        ),
        Paragraph(
            'Projection compares current utilization percentage against projected utilization at the end of the forecast horizon.',  # noqa: E501
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
                2.8 * cm,
                3.3 * cm,
                2.4 * cm,
                2.6 * cm,
                2.0 * cm,
                3.1 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_forecast_threshold_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    items = _as_pdf_list(
        forecast_payload.get(
            'items',
            [],
        )
    )

    rows = [
        [
            'Resource',
            'Warning ETA',
            'Critical ETA',
            'Confidence Reason',
        ],
    ]

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
                format_forecast_eta(
                    item.get(
                        'warning_eta',
                        {},
                    )
                ),
                format_forecast_eta(
                    item.get(
                        'critical_eta',
                        {},
                    )
                ),
                _pdf_value(
                    item.get(
                        'confidence_reason',
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
                'No threshold ETA data available.',
            ]
        )

    return [
        Paragraph(
            'Nearest Warning / Critical Threshold',
            styles['small_section_title'],
        ),
        Paragraph(
            'ETA values are calculated from the projected linear growth rate. "Not projected" means the metric is not expected to reach the threshold in the selected horizon.',  # noqa: E501
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
                2.8 * cm,
                3.4 * cm,
                3.4 * cm,
                6.6 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_forecast_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    forecast_payload = (
        payload.get(
            'forecast_payload',
        )
        or {}
    )

    recommendations = forecast_payload.get(
        'actionable_recommendations',
        [],
    )

    if not isinstance(
        recommendations,
        list,
    ):
        recommendations = []

    if not recommendations:
        recommendations = build_forecast_actionable_recommendations(
            forecast_payload,
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
                'Review forecast trend',
                'Info',
                'Forecast baseline',
            ]
        )
        rows.append(
            [
                '',
                'No forecast recommendation was generated. Continue monitoring projected resource growth and confidence level.',  # noqa: E501
                'Context',
                '',
            ]
        )

    return [
        Paragraph(
            'Actionable Recommendations from Resource Forecast',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from projected utilization, warning/critical thresholds, '
                'threshold ETA, growth slope, and forecast confidence. Critical and Warning items are actionable.'
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
